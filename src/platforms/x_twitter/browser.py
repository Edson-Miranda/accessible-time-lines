"""
Gerenciador do ciclo de vida do navegador Chromium para o X.
Utiliza perfil de dados persistente (mantendo cookies e sessão).
Executa em modo 100% headless (sem qualquer janela) quando autenticado,
garantindo que o navegador nunca apareça na tela nem interfira na navegação.
"""

import json
import logging
import os
from pathlib import Path
import queue
import shutil
import sqlite3
import threading
import time
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, BrowserContext, Page, Response
from src.platforms.x_twitter.parser import parse_x_graphql_response
from src.core.models import Post

logger = logging.getLogger("AccessibleTimeline.Browser")


def is_profile_authenticated(data_dir: str) -> bool:
    """Verifica diretamente se a sessão já está autenticada no banco de cookies."""
    cookie_file = Path(data_dir) / "Default" / "Network" / "Cookies"
    if not cookie_file.exists():
        return False
    try:
        temp_db = Path(data_dir) / "temp_check_auth.db"
        shutil.copy2(cookie_file, temp_db)
        conn = sqlite3.connect(temp_db)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM cookies WHERE name = 'auth_token' LIMIT 1")
        has_auth = cur.fetchone() is not None
        conn.close()
        if temp_db.exists():
            os.remove(temp_db)
        return has_auth
    except Exception:
        return False


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
        self._account_name: Optional[str] = None
        self._force_visible = False
        self._current_headless: Optional[bool] = None

        self.on_posts_callback: Optional[Callable[[str, list[Post]], None]] = None
        self.on_status_callback: Optional[Callable[[str], None]] = None
        self.on_account_info_callback: Optional[Callable[[str], None]] = None

    def toggle_browser_window(self):
        """Alterna a visibilidade da janela do navegador."""
        self._cmd_queue.put(("toggle_visibility", None))

    def is_browser_visible(self) -> bool:
        """Indica se o navegador está atualmente em modo com janela visível."""
        return self._current_headless is False

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
        on_account_info: Optional[Callable[[str], None]] = None
    ):
        """Inicia a thread de trabalho do navegador."""
        self.on_posts_callback = on_posts
        self.on_status_callback = on_status
        self.on_account_info_callback = on_account_info
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

    def switch_feed_tab(self, feed: str):
        """Alterna o fluxo no site do X ('for_you', 'following', 'mentions', 'dms')."""
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

    def execute_action(self, action_name: str, timeout: float = 35.0, **kwargs) -> bool:
        """Envia comando de ação para a thread do navegador e aguarda a conclusão."""
        if not self._running:
            return False
        event = threading.Event()
        res_holder = {"success": False}
        self._cmd_queue.put(("action", (action_name, kwargs, event, res_holder)))
        event.wait(timeout=timeout)
        return res_holder["success"]

    def _do_create_post(self, page: Page, text: str) -> bool:
        """Cria e envia uma nova publicação no X."""
        logger.info("Executando postagem de tweet...")
        self._set_status("Enviando publicação para o X...")
        try:
            page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=25000)
            box = page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=15000)
            if not box:
                return False
            box.click()
            box.fill(text)
            time.sleep(0.5)

            btn = page.wait_for_selector('[data-testid="tweetButton"]', timeout=8000)
            if btn and btn.is_enabled():
                btn.click()
                time.sleep(2.5)
                self._set_status("Publicação enviada com sucesso!")
                return True
            else:
                self._set_status("Erro: Botão de publicação não habilitado.")
                return False
        except Exception as e:
            logger.error(f"Erro ao criar post: {e}")
            self._set_status(f"Falha ao publicar: {e}")
            return False

    def _do_reply_to_post(self, page: Page, post_id: str, text: str, author_username: str = "") -> bool:
        """Responde a uma publicação existente no X."""
        logger.info(f"Executando resposta ao post {post_id}...")
        self._set_status(f"Enviando resposta para @{author_username or 'post'}...")
        try:
            url = f"https://x.com/i/status/{post_id}"
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            box = page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=15000)
            if not box:
                return False
            box.click()
            box.fill(text)
            time.sleep(0.5)

            btn = page.locator('[data-testid="tweetButtonInline"], [data-testid="tweetButton"]').first
            if btn.is_visible() and btn.is_enabled():
                btn.click()
                time.sleep(2.5)
                self._set_status("Resposta enviada com sucesso!")
                return True
            else:
                self._set_status("Erro: Botão de resposta não habilitado.")
                return False
        except Exception as e:
            logger.error(f"Erro ao responder: {e}")
            self._set_status(f"Falha ao responder: {e}")
            return False

    def _do_retweet_post(self, page: Page, post_id: str) -> bool:
        """Reposta (retweet simples) uma publicação no X."""
        logger.info(f"Executando retweet do post {post_id}...")
        self._set_status("Repostando publicação no X...")
        try:
            url = f"https://x.com/i/status/{post_id}"
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(1.0)
            rt_btn = page.wait_for_selector('[data-testid="retweet"]', timeout=12000)
            if not rt_btn:
                if page.locator('[data-testid="unretweet"]').count() > 0:
                    self._set_status("Esta publicação já foi repostada.")
                    return True
                return False
            rt_btn.click()
            time.sleep(0.5)

            confirm_btn = page.wait_for_selector('[data-testid="retweetConfirm"]', timeout=6000)
            if confirm_btn:
                confirm_btn.click()
                time.sleep(1.5)
                self._set_status("Publicação repostada com sucesso!")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao repostar: {e}")
            self._set_status(f"Falha ao repostar: {e}")
            return False

    def _do_quote_post(self, page: Page, post_id: str, text: str, tweet_url: str = "") -> bool:
        """Reposta com comentário (citar publicação) no X."""
        logger.info(f"Executando citação do post {post_id}...")
        self._set_status("Publicando citação no X...")
        try:
            target_url = tweet_url or f"https://x.com/i/status/{post_id}"
            full_quote_text = f"{text.strip()} {target_url}"

            page.goto("https://x.com/compose/post", wait_until="domcontentloaded", timeout=25000)
            box = page.wait_for_selector('[data-testid="tweetTextarea_0"]', timeout=15000)
            if not box:
                return False
            box.click()
            box.fill(full_quote_text)
            time.sleep(1.0)

            btn = page.wait_for_selector('[data-testid="tweetButton"]', timeout=8000)
            if btn and btn.is_enabled():
                btn.click()
                time.sleep(2.5)
                self._set_status("Citação publicada com sucesso!")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao citar post: {e}")
            self._set_status(f"Falha ao publicar citação: {e}")
            return False

    def _do_like_post(self, page: Page, post_id: str) -> bool:
        """Curte uma publicação no X."""
        logger.info(f"Executando curtida no post {post_id}...")
        self._set_status("Curtindo publicação...")
        try:
            url = f"https://x.com/i/status/{post_id}"
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(1.0)

            if page.locator('[data-testid="unlike"]').count() > 0:
                self._set_status("A publicação já está curtida.")
                return True

            like_btn = page.wait_for_selector('[data-testid="like"]', timeout=10000)
            if like_btn:
                like_btn.click()
                time.sleep(1.5)
                self._set_status("Publicação curtida com sucesso!")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao curtir post: {e}")
            self._set_status(f"Falha ao curtir publicação: {e}")
            return False

    def _do_unlike_post(self, page: Page, post_id: str) -> bool:
        """Remove a curtida (descurtir) de uma publicação no X."""
        logger.info(f"Executando descurtida no post {post_id}...")
        self._set_status("Descurtindo publicação...")
        try:
            url = f"https://x.com/i/status/{post_id}"
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            time.sleep(1.0)

            unlike_btn = page.wait_for_selector('[data-testid="unlike"]', timeout=10000)
            if unlike_btn:
                unlike_btn.click()
                time.sleep(1.5)
                self._set_status("Curtida removida com sucesso!")
                return True
            else:
                self._set_status("A publicação não estava curtida.")
                return True
        except Exception as e:
            logger.error(f"Erro ao descurtir post: {e}")
            self._set_status(f"Falha ao descurtir publicação: {e}")
            return False

    def _do_send_dm(self, page: Page, recipient: str, text: str) -> bool:
        """Envia mensagem direta (DM) no X."""
        clean_user = recipient.lstrip("@").strip()
        logger.info(f"Enviando DM para @{clean_user}...")
        self._set_status(f"Enviando mensagem direta para @{clean_user}...")
        try:
            page.goto("https://x.com/messages/compose", wait_until="domcontentloaded", timeout=25000)
            search_input = page.wait_for_selector('input[data-testid="searchPeople"]', timeout=15000)
            if not search_input:
                search_input = page.wait_for_selector('input[type="text"]', timeout=8000)
            if not search_input:
                return False

            search_input.fill(clean_user)
            time.sleep(1.5)

            user_row = page.wait_for_selector('[data-testid="TypeaheadUser"]', timeout=10000)
            if user_row:
                user_row.click()
                time.sleep(0.5)

            next_btn = page.wait_for_selector('[data-testid="nextButton"]', timeout=6000)
            if next_btn and next_btn.is_enabled():
                next_btn.click()
                time.sleep(1.5)

            dm_box = page.wait_for_selector('[data-testid="dmComposerTextInput"]', timeout=12000)
            if not dm_box:
                dm_box = page.wait_for_selector('div[contenteditable="true"]', timeout=8000)
            if not dm_box:
                return False

            dm_box.click()
            dm_box.fill(text)
            time.sleep(0.5)

            send_btn = page.locator('[data-testid="dmComposerSendButton"]').first
            if send_btn.is_visible() and send_btn.is_enabled():
                send_btn.click()
            else:
                dm_box.press("Enter")

            time.sleep(2.0)
            self._set_status(f"Mensagem direta enviada para @{clean_user} com sucesso!")
            return True
        except Exception as e:
            logger.error(f"Erro ao enviar DM: {e}")
            self._set_status(f"Falha ao enviar DM: {e}")
            return False

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

    def _click_tab_by_name(self, page: Page, feed_name: str) -> bool:
        """Clica na aba especificada usando locators nativos do Playwright com fallback JS."""
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

        if "/home" not in page.url:
            try:
                page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
                time.sleep(1.0)
            except Exception:
                pass

        try:
            import re
            if feed_name == "following":
                loc = page.locator('[role="tab"]').filter(has_text=re.compile(r"seguindo|following", re.I))
                if loc.count() > 0:
                    loc.first.click(timeout=4000)
                    return True
                tabs = page.locator('[role="tab"]')
                if tabs.count() >= 2:
                    tabs.nth(1).click(timeout=4000)
                    return True
            elif feed_name in ("for_you", "home"):
                loc = page.locator('[role="tab"]').filter(has_text=re.compile(r"para voc|for you", re.I))
                if loc.count() > 0:
                    loc.first.click(timeout=4000)
                    return True
                tabs = page.locator('[role="tab"]')
                if tabs.count() >= 1:
                    tabs.nth(0).click(timeout=4000)
                    return True
        except Exception as e:
            logger.debug(f"Locator click falhou, tentando fallback JS: {e}")

        return self._execute_tab_switch_js(page, feed_name)

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
        if "/i/api/" in url:
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        payload = response.json()
                    except Exception:
                        body = response.text()
                        if not body:
                            return
                        payload = json.loads(body)

                    posts = parse_x_graphql_response(payload)
                    if posts:
                        if "HomeLatestTimeline" in url:
                            feed_type = "following"
                        elif "Notifications" in url or "notifications" in url:
                            feed_type = "mentions"
                        elif "dm" in url or "messages" in url:
                            feed_type = "dms"
                        else:
                            feed_type = "for_you"

                        logger.info(f"Interceptadas {len(posts)} publicações para o fluxo '{feed_type}'")
                        if self.on_posts_callback:
                            self.on_posts_callback(feed_type, posts)
            except Exception as e:
                logger.debug(f"Aviso ao processar resposta: {e}")

    def _preload_all_tabs(self, page: Page):
        """
        Navega pelas guias principais ao abrir o programa para carregar
        e capturar o conteúdo de cada fluxo, atualizando a barra de status.
        """
        logger.info("Iniciando pré-carregamento de todas as guias...")

        # 1. Carrega fluxo Para você (Home inicial)
        self._set_status("Carregando fluxo Para você...")
        try:
            page.wait_for_selector('[role="tab"]', timeout=15000)
            self._click_tab_by_name(page, "for_you")
        except Exception as e:
            logger.debug(f"Aviso ao aguardar/selecionar aba Para você: {e}")
        time.sleep(3.5)
        self._detect_account_info(page)

        if not self._running:
            return

        # 2. Carrega fluxo Seguindo
        self._set_status("Carregando fluxo Seguindo...")
        try:
            self._click_tab_by_name(page, "following")
        except Exception as e:
            logger.debug(f"Aviso ao selecionar aba Seguindo: {e}")
        time.sleep(3.5)
        self._detect_account_info(page)

        if not self._running:
            return

        # 3. Carrega fluxo Menções e Notificações
        self._set_status("Carregando Menções e Notificações...")
        try:
            page.goto("https://x.com/notifications", wait_until="domcontentloaded", timeout=25000)
        except Exception as e:
            logger.debug(f"Aviso ao navegar para notificações: {e}")
        time.sleep(3.5)
        self._detect_account_info(page)

        if not self._running:
            return

        # 4. Retorna para a página inicial (fluxo Para você)
        self._set_status("Finalizando carregamento e retornando ao fluxo principal...")
        try:
            page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_selector('[role="tab"]', timeout=15000)
            self._click_tab_by_name(page, "for_you")
        except Exception as e:
            logger.debug(f"Aviso ao retornar para página inicial: {e}")
        time.sleep(1.5)
        self._detect_account_info(page)

        self._set_status("Pronto. Publicações carregadas.")

    def _launch_persistent_context_with_fallback(
        self,
        pw,
        headless: bool
    ) -> BrowserContext:
        """
        Inicia o Chromium com estratégia de fallback transparente:
        1. Microsoft Edge do sistema operacional (channel='msedge')
        2. Google Chrome (channel='chrome')
        3. Chromium do Playwright (channel=None)
        4. Auto-instalação caso nenhum navegador exista
        """
        channels_to_try = ["msedge", "chrome", None]
        common_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        for ch in channels_to_try:
            try:
                kwargs = {
                    "user_data_dir": self.data_dir,
                    "headless": headless,
                    "viewport": {"width": 1280, "height": 800},
                    "args": common_args,
                }
                if ch:
                    kwargs["channel"] = ch
                ctx = pw.chromium.launch_persistent_context(**kwargs)
                logger.info(f"Navegador iniciado com sucesso (canal={ch or 'padrão'}, headless={headless})")
                return ctx
            except Exception as e:
                logger.debug(f"Tentativa de iniciar navegador via canal '{ch}' falhou: {e}")
                continue

        # Se todos os navegadores locais falharem, dispara auto-instalação
        logger.warning("Nenhum navegador Chromium encontrado. Baixando componentes...")
        self._set_status("Instalando componentes do navegador pela primeira vez. Por favor, aguarde...")
        self._auto_install_chromium()

        return pw.chromium.launch_persistent_context(
            user_data_dir=self.data_dir,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=common_args,
        )

    def _auto_install_chromium(self):
        """Executa 'playwright install chromium' via subprocess de forma resiliente."""
        import subprocess
        import sys
        try:
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, timeout=180)
        except Exception as e:
            logger.error(f"Falha ao executar auto-instalação do Chromium: {e}")

    def _worker_loop(self):
        """Loop executado na thread de segundo plano."""
        while self._running:
            is_authenticated = is_profile_authenticated(self.data_dir)
            headless = is_authenticated and not self._force_visible
            self._current_headless = headless

            if headless:
                self._set_status("Iniciando motor de acesso ao X (modo em segundo plano)...")
            else:
                self._set_status("Aguardando login no navegador. Por favor, faça login na janela aberta...")

            with sync_playwright() as pw:
                try:
                    context: BrowserContext = self._launch_persistent_context_with_fallback(pw, headless=headless)
                    context.on("response", self._handle_response)
                    page: Page = context.pages[0] if context.pages else context.new_page()

                    try:
                        page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=45000)
                    except Exception as e:
                        logger.warning(f"Aviso no carregamento inicial: {e}")

                    # Se estava com janela aberta para login inicial (não forçada manualmente)
                    if not headless and not self._force_visible:
                        logged_in = False
                        while self._running and not logged_in and not self._force_visible:
                            time.sleep(1.5)
                            try:
                                cookies = context.cookies()
                                for c in cookies:
                                    if c.get("name") == "auth_token":
                                        logged_in = True
                                        break
                            except Exception:
                                pass
                        if logged_in:
                            self._set_status("Login concluído com sucesso! Ocultando navegador...")
                            context.close()
                            continue

                    self._detect_account_info(page)

                    # Navega nas guias para carregar o conteúdo de cada uma na inicialização
                    self._preload_all_tabs(page)

                    # Loop de comandos durante a execução normal
                    while self._running:
                        try:
                            cmd, arg = self._cmd_queue.get(timeout=0.2)
                            if cmd == "stop":
                                context.close()
                                return
                            elif cmd == "toggle_visibility":
                                self._force_visible = not self._force_visible
                                status_txt = "Abrindo janela do navegador..." if self._force_visible else "Ocultando janela do navegador..."
                                self._set_status(status_txt)
                                context.close()
                                break
                            elif cmd == "switch_tab":
                                feed_name = arg
                                self._set_status(f"Acessando fluxo {feed_name}...")
                                self._click_tab_by_name(page, feed_name)
                                self._detect_account_info(page)
                            elif cmd == "navigate":
                                url = arg
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
                            elif cmd == "action":
                                action_name, kwargs, event, res_holder = arg
                                try:
                                    if action_name == "create_post":
                                        res_holder["success"] = self._do_create_post(page, **kwargs)
                                    elif action_name == "reply_to_post":
                                        res_holder["success"] = self._do_reply_to_post(page, **kwargs)
                                    elif action_name == "retweet_post":
                                        res_holder["success"] = self._do_retweet_post(page, **kwargs)
                                    elif action_name == "quote_post":
                                        res_holder["success"] = self._do_quote_post(page, **kwargs)
                                    elif action_name == "like_post":
                                        res_holder["success"] = self._do_like_post(page, **kwargs)
                                    elif action_name == "unlike_post":
                                        res_holder["success"] = self._do_unlike_post(page, **kwargs)
                                    elif action_name == "send_dm":
                                        res_holder["success"] = self._do_send_dm(page, **kwargs)
                                except Exception as act_err:
                                    logger.error(f"Erro ao executar ação {action_name}: {act_err}")
                                    res_holder["success"] = False
                                finally:
                                    event.set()
                        except queue.Empty:
                            pass

                        time.sleep(0.05)

                    try:
                        context.close()
                    except Exception:
                        pass
                except Exception as e:
                    logger.error(f"Erro no motor do navegador: {e}")
                    self._set_status(f"Erro no navegador: {e}")
                    time.sleep(2.0)
