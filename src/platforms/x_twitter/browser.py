"""
Gerenciador do ciclo de vida do navegador Chromium para o X.
Utiliza perfil de dados persistente (mantendo cookies e sessão).
Executa em thread dedicada em segundo plano com fila de comandos sem bloquear a interface gráfica.
Permite exibir ou ocultar a janela do navegador a qualquer momento.
"""

import ctypes
import json
import logging
import os
from pathlib import Path
import queue
import threading
import time
from typing import Callable, Optional
from playwright.sync_api import sync_playwright, BrowserContext, Page, Response
from src.platforms.x_twitter.parser import parse_x_graphql_response
from src.core.models import Post

logger = logging.getLogger("AccessibleTimeline.Browser")

# Constantes Win32 para ShowWindow
SW_HIDE = 0
SW_NORMAL = 1
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9


def _find_browser_windows(pid: int) -> list[int]:
    """Localiza as janelas pertencentes ao processo do navegador via Win32 API."""
    hwnds = []

    def enum_windows_callback(hwnd, extra):
        if ctypes.windll.user32.IsWindowVisible(hwnd) or True:
            window_pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
            if window_pid.value == pid:
                # Verifica se tem título ou estilo de janela principal
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value
                    if "Twitter" in title or "X" in title or "Chrome" in title:
                        hwnds.append(hwnd)
        return True

    try:
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
        ctypes.windll.user32.EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
    except Exception as e:
        logger.warning(f"Erro ao enumerar janelas: {e}")

    return hwnds


class XBrowserManager:
    def __init__(self, data_dir: Optional[str] = None):
        if data_dir is None:
            # Salva no diretório de dados da aplicação
            base_dir = Path(os.environ.get("APPDATA", ".")) / "AccessibleTimeline"
            data_dir = str(base_dir / "x_profile")

        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self._thread: Optional[threading.Thread] = None
        self._cmd_queue: queue.Queue = queue.Queue()
        self._running = False
        self._is_visible = True
        self._browser_hwnds: list[int] = []
        self._browser_pid: Optional[int] = None

        self.on_posts_callback: Optional[Callable[[list[Post]], None]] = None
        self.on_status_callback: Optional[Callable[[str], None]] = None

    def _set_status(self, text: str):
        logger.info(f"Status: {text}")
        if self.on_status_callback:
            try:
                self.on_status_callback(text)
            except Exception as e:
                logger.error(f"Erro no callback de status: {e}")

    def start(self, on_posts: Callable[[list[Post]], None], on_status: Optional[Callable[[str], None]] = None, start_visible: bool = True):
        """Inicia a thread do navegador."""
        self.on_posts_callback = on_posts
        self.on_status_callback = on_status
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
        """Torna a janela do navegador visível."""
        self._is_visible = True
        self._cmd_queue.put(("set_visibility", True))

    def hide_browser(self):
        """Oculta a janela do navegador da área de trabalho."""
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

    def reload_timeline(self):
        """Comanda a página do X a recarregar a timeline."""
        self._cmd_queue.put(("reload", None))

    def scroll_down(self):
        """Comanda a página a rolar para baixo para carregar mais publicações."""
        self._cmd_queue.put(("scroll_down", None))

    def _apply_window_visibility(self, visible: bool):
        """Aplica visibilidade usando Win32 ShowWindow nos HWNDs do navegador."""
        if not self._browser_pid:
            return

        hwnds = _find_browser_windows(self._browser_pid)
        if not hwnds and self._browser_hwnds:
            hwnds = self._browser_hwnds
        else:
            self._browser_hwnds = hwnds

        for hwnd in hwnds:
            if visible:
                ctypes.windll.user32.ShowWindow(hwnd, SW_RESTORE)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
            else:
                ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)

    def _handle_response(self, response: Response):
        """Intercepta passivamente respostas de rede da API do X."""
        url = response.url
        # Filtra chamadas GraphQL e endpoints de timeline da API do X
        if "/i/api/graphql/" in url or "/i/api/2/" in url:
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = response.text()
                    if body:
                        payload = json.loads(body)
                        posts = parse_x_graphql_response(payload)
                        if posts and self.on_posts_callback:
                            self.on_posts_callback(posts)
            except Exception as e:
                # Resposta pode não ser JSON ou ter sido abortada
                pass

    def _worker_loop(self):
        """Loop executado na thread de segundo plano."""
        self._set_status("Iniciando navegador...")

        with sync_playwright() as pw:
            try:
                # Iniciamos com navegador real Chromium mantendo o perfil persistente
                context: BrowserContext = pw.chromium.launch_persistent_context(
                    user_data_dir=self.data_dir,
                    headless=False,  # Headed para permitir login, 2FA e visibilidade sob demanda
                    viewport={"width": 1280, "height": 800},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                )

                page: Page = context.pages[0] if context.pages else context.new_page()

                # Escuta passiva de respostas de rede
                page.on("response", self._handle_response)

                self._set_status("Acessando X (antigo Twitter)...")
                try:
                    page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=45000)
                except Exception as e:
                    logger.warning(f"Aviso no carregamento inicial: {e}")

                self._set_status("Pronto. Monitorando publicações da timeline...")

                # Loop de comandos e manutenção
                last_check_time = time.time()
                while self._running:
                    # Processa comandos da fila
                    try:
                        cmd, arg = self._cmd_queue.get(timeout=0.2)
                        if cmd == "stop":
                            break
                        elif cmd == "set_visibility":
                            self._apply_window_visibility(arg)
                        elif cmd == "reload":
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

                    # Mantém o loop responsivo
                    time.sleep(0.05)

                context.close()
            except Exception as e:
                logger.error(f"Erro crítico no navegador: {e}")
                self._set_status(f"Erro no navegador: {e}")
            finally:
                self._running = False
                self._set_status("Navegador finalizado.")
