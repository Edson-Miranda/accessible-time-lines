"""
Leitor de timeline do X (Twitter).
Implementa BaseTimelineReader, isolando a leitura e a conversão de publicações.
"""

from typing import Callable, List, Optional
from src.core.models import Post
from src.platforms.base import BaseTimelineReader
from src.platforms.x_twitter.browser import XBrowserManager


class XTimelineReader(BaseTimelineReader):
    """
    Controla a obtenção passiva de publicações do X através do navegador.
    Totalmente separado de qualquer rotina de escrita ou interação.
    """
    def __init__(self, browser_manager: Optional[XBrowserManager] = None):
        self.browser_manager = browser_manager or XBrowserManager()

    def start(self, on_posts_received: Callable[[List[Post]], None], on_status_change: Optional[Callable[[str], None]] = None):
        """Inicia a captura e monitoramento passivo de publicações."""
        self.browser_manager.start(
            on_posts=on_posts_received,
            on_status=on_status_change,
            start_visible=True  # Exibe no início para o usuário fazer login se necessário
        )

    def stop(self):
        """Interrompe a captura."""
        self.browser_manager.stop()

    def refresh(self):
        """Solicita recarregamento da timeline."""
        self.browser_manager.reload_timeline()

    def load_more(self):
        """Solicita rolagem para carregar mais publicações."""
        self.browser_manager.scroll_down()

    def toggle_browser_visibility(self):
        """Alterna a visibilidade da janela do navegador."""
        self.browser_manager.toggle_browser_visibility()

    def is_browser_visible(self) -> bool:
        return self.browser_manager.is_browser_visible()
