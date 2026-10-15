"""
Gerenciador do ciclo de vida do navegador Chromium para o X.
Utiliza perfil de dados persistente (mantendo cookies e sessão).
Executa em thread dedicada em segundo plano com fila de comandos sem bloquear a interface gráfica.
Controla a visibilidade via CDP e gerencia os fluxos de Para você, Seguindo, Notificações e DMs.
"""

import json
import logging
import os
from pathlib import Path
import queue
import threading
import time
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, BrowserContext, Page, Response, CDPSession
from src.platforms.x_twitter.parser import parse_x_graphql_response
from src.core.models import Post

logger = logging.getLogger("AccessibleTimeline.Browser")


class XBrowserManager:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            base_dir = Path(os.environ.get("APPDATA", ".")) / "AccessibleTimeline"
            data_dir = str(base_dir / "x_profile")

        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self._thread: Optional[threading.Thread] = None
        self._cmd_queue: queue.Queue = queue.Queue()
        self._running = False
        self._is_visible = False
        self._logged_in = False
        self._posts_received_count = 0
        self._cdp: Optional[CDPSession] = None
        self._account_name: Optional[str] = None

        self.on_posts_callback: Optional[Callable[[str, list[Post]], None]] = None
        self.on_status_callback: Optional[Callable[[str], None]] = None
        self.on_account_info_callback: Optional[Callable[[str], None]] = None

    def _set_status(self, text: str):
        logger.info(f"Status: {text}")
        if self.on_status_callback:
            try:
                self.on_status_callback(text)
            except Exception as e:
                logger.error(f"Erro no callback de status: {e}")

    def start(
        self,
        on_posts: Callable[[str, list[Post]], None],
        on_status: Optional[Callable[[str], None]] = None,
        on_account_info: Optional[Callable[[str], None]] = None,
        start_visible: bool = False
    ):
        """Inicia a thread do navegador."""
        self.on_posts_callback = on_posts
        self.on_status_callback = on_status
        self.on_account_info_callback = on_account_info
        self._is_visible = start_visible
        self._running = True

        self._thread = threading.Thread(target=self._worker_loop, name="XBrowserWorker", daemon=True)
        self._thread.start()

    def stop(self):
        """Para o navegador e finaliza a thread de trabalho."""
        if not self._running:
            return
        self._running = False
        self._cmd_queue.put(("stop", None))
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def show_browser(self):
        """Restaura a janela do navegador na tela."""
        self._is_visible = True
        self._cmd_queue.put(("set_visibility", True))

    def hide_browser(self):
        """Minimiza/oculta a janela do navegador da área de trabalho."""
        self._is_visible = False
        self._cmd_queue.put(("set_visibility", False))

    def toggle_browser_visibility(self):
        """Alterna a visibilidade da janela do navegador."""
        if self._is_visible:
            self.hide_browser()
        else:
            self.show_browser()

    def is_browser_visible(self) -> bool:
        return self._is_visible

    def switch_feed_tab(self, feed: str):
        """Alterna a aba de conteúdo no site do X ('for_you', 'following', 'mentions', 'dms')."""
        self._cmd_queue.put(("switch_tab", feed))

    def navigate_to(self, url: str):
        """Navega para uma URL específica."""
        self._cmd_queue.put(("navigate", url))

    def reload_timeline(self, feed: Optional[str] = None):
        """Comanda a página do X a recarregar a timeline."""
        self._cmd_queue.put(("reload", feed))

    def scroll_down(self):
        """Comanda a página a rolar para baixo para carregar mais publicações."""
        self._cmd_queue.put(("scroll_down", None))

    def _apply_cdp_visibility(self, visible: bool):
        """Aplica visibilidade usando Chrome DevTools Protocol nativo."""
        if not self._cdp:
            return
        try:
            win = self._cdp.send("Browser.getWindowForTarget")
            window_id = win.get("windowId")
            if window_id:
                state = "normal" if visible else "minimized"
                self._cdp.send("Browser.setWindowBounds", {
                    "windowId": window_id,
                    "bounds": {"windowState": state}
                })
                logger.info(f"Visibilidade do navegador ajustada para: {state}")
        except Exception as e:
            logger.warning(f"Aviso ao ajustar visibilidade via CDP: {e}")

    def _detect_account_info(self, page: Page):
        """Tenta extrair o nome e usuário da conta conectada."""
        js_code = """
        () => {
            const btn = document.querySelector('[data-testid="SideNav_AccountSwitcher_Button"]');
            if (btn) {
                const lines = (btn.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
                if (lines.length >= 2) {
                    return lines[0] + ' (' + lines[1] + ')';
                } else if (lines.length === 1) {
                    return lines[0];
                }
            }
            return null;
        }
        """
        try:
            acc = page.evaluate(js_code)
            if acc and acc != self._account_name:
                self._account_name = acc
                logger.info(f"Conta conectada detectada: {acc}")
                if self.on_account_info_callback:
                    self.on_account_info_callback(acc)
        except Exception:
            pass

    def _execute_tab_switch_js(self, page: Page, feed_name: str) -> bool:
        """Executa clique seguro na aba do X via JavaScript no DOM."""
        if feed_name in ("mentions", "notifications"):
            try:
                page.goto("https://x.com/notifications", wait_until="domcontentloaded", timeout=25000)
                return True
            except Exception as e:
                logger.warning(f"Erro ao navegar para notificações: {e}")
                return False
        elif feed_name in ("dms", "messages"):
            try:
                page.goto("https://x.com/messages", wait_until="domcontentloaded", timeout=25000)
                return True
            except Exception as e:
                logger.warning(f"Erro ao navegar para mensagens: {e}")
                return False

        # Se não estiver em /home, navega para /home primeiro
        if "/home" not in page.url:
            try:
                page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
                time.sleep(1.0)
            except Exception:
                pass

        js_code = """
        (targetFeed) => {
            const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
            for (const t of tabs) {
                const text = (t.innerText || t.textContent || '').trim().toLowerCase();
                if (targetFeed === 'following' && (text.includes('seguindo') || text.includes('following'))) {
                    t.click();
                    return true;
                } else if ((targetFeed === 'for_you' || targetFeed === 'home') && (text.includes('para você') || text.includes('para voce') || text.includes('for you'))) {
                    t.click();
                    return true;
                }
            }
            if (tabs.length >= 2) {
                const idx = targetFeed === 'following' ? 1 : 0;
                tabs[idx].click();
                return true;
            }
            return false;
        }
        """
        try:
            return bool(page.evaluate(js_code, feed_name))
        except Exception as e:
            logger.warning(f"Erro ao alternar aba via JS: {e}")
            return False

    def _handle_response(self, response: Response):
        """Intercepta passivamente respostas de rede da API do X e roteia para o feed correto."""
        url = response.url
        if "/i/api/graphql/" in url or "/i/api/2/" in url:
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = response.text()
                    if body:
                        payload = json.loads(body)
                        posts = parse_x_graphql_response(payload)
                        if posts:
                            self._posts_received_count += len(posts)

                            # Identifica o fluxo de destino
                            if "HomeLatestTimeline" in url:
                                feed_type = "following"
                            elif "Notifications" in url or "notifications" in url:
                                feed_type = "mentions"
                            elif "dm" in url or "messages" in url:
                                feed_type = "dms"
                            else:
                                feed_type = "for_you"

                            logger.info(f"Interceptadas {len(posts)} publicações para o fluxo '{feed_type}' de {url}")
                            if self.on_posts_callback:
                                self.on_posts_callback(feed_type, posts)
            except Exception as e:
                logger.debug(f"Aviso ao processar resposta: {e}")

    def _check_auth_status(self, context: BrowserContext) -> bool:
        """Verifica se os cookies essenciais de autenticação do X estão presentes."""
        try:
            cookies = context.cookies()
            for c in cookies:
                if "x.com" in c.get("domain", "") or "twitter.com" in c.get("domain", ""):
                    if c.get("name") == "auth_token":
                        return True
        except Exception:
            pass
        return False

    def _worker_loop(self):
        """Loop executado na thread de segundo plano."""
        self._set_status("Iniciando navegador...")

        with sync_playwright() as pw:
            try:
                context: BrowserContext = pw.chromium.launch_persistent_context(
                    user_data_dir=self.data_dir,
                    headless=False,
                    viewport={"width": 1280, "height": 800},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                )

                context.on("response", self._handle_response)
                page: Page = context.pages[0] if context.pages else context.new_page()

                try:
                    self._cdp = context.new_cdp_session(page)
                except Exception as e:
                    logger.warning(f"Não foi possível iniciar CDP session: {e}")

                already_authenticated = self._check_auth_status(context)
                self._logged_in = already_authenticated

                if already_authenticated:
                    self._set_status("Sessão autenticada detectada. Acessando timeline...")
                    self._is_visible = False
                    self._apply_cdp_visibility(False)
                else:
                    self._set_status("Aguardando login no navegador. Pressione F11 se precisar exibir a janela.")
                    self._is_visible = True

                try:
                    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    logger.warning(f"Aviso no carregamento inicial: {e}")

                if self._logged_in:
                    self._apply_cdp_visibility(False)
                    self._is_visible = False

                time.sleep(2.0)
                if self._logged_in:
                    self._detect_account_info(page)
                    # Pré-carrega Seguindo e retorna a Para você
                    self._execute_tab_switch_js(page, "following")
                    time.sleep(2.0)
                    self._execute_tab_switch_js(page, "for_you")
                    self._apply_cdp_visibility(False)

                last_auth_check = time.time()

                # Loop de comandos e manutenção
                while self._running:
                    try:
                        cmd, arg = self._cmd_queue.get(timeout=0.2)
                        if cmd == "stop":
                            break
                        elif cmd == "set_visibility":
                            self._apply_cdp_visibility(arg)
                        elif cmd == "switch_tab":
                            feed_name = arg
                            label_map = {
                                "for_you": "Para você",
                                "following": "Seguindo",
                                "mentions": "Menções",
                                "dms": "Mensagens diretas"
                            }
                            display_name = label_map.get(feed_name, feed_name)
                            self._set_status(f"Acessando {display_name}...")
                            self._execute_tab_switch_js(page, feed_name)
                            self._detect_account_info(page)
                        elif cmd == "navigate":
                            url = arg
                            self._set_status(f"Navegando...")
                            try:
                                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                            except Exception as e:
                                logger.warning(f"Erro ao navegar: {e}")
                        elif cmd == "reload":
                            feed_name = arg
                            if feed_name:
                                self._execute_tab_switch_js(page, feed_name)
                            self._set_status("Atualizando página do X...")
                            try:
                                page.reload(wait_until="domcontentloaded", timeout=30000)
                                self._set_status("Timeline atualizada.")
                            except Exception as e:
                                self._set_status(f"Erro ao atualizar: {e}")
                        elif cmd == "scroll_down":
                            self._set_status("Carregando mais postagens...")
                            try:
                                page.evaluate("window.scrollBy(0, window.innerHeight * 2);")
                            except Exception as e:
                                logger.warning(f"Erro ao rolar: {e}")
                    except queue.Empty:
                        pass

                    now = time.time()
                    if now - last_auth_check > 2.0:
                        last_auth_check = now
                        is_auth = self._check_auth_status(context)
                        if is_auth and not self._logged_in:
                            self._logged_in = True
                            self._set_status("Login detectado com sucesso! Carregando timelines...")
                            self._apply_cdp_visibility(False)
                            self._is_visible = False
                            self._detect_account_info(page)
                            if self._posts_received_count == 0:
                                try:
                                    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)
                                except Exception as e:
                                    logger.warning(f"Erro ao navegar para home após login: {e}")

                    time.sleep(0.05)

                context.close()
            except Exception as e:
                logger.error(f"Erro crítico no navegador: {e}")
                self._set_status(f"Erro no navegador: {e}")
            finally:
                self._running = False
                self._set_status("Navegador finalizado.")
