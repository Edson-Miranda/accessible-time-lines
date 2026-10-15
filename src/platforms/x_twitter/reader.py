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

    def start(
        self,
        on_posts_received: Callable[[str, List[Post]], None],
        on_status_change: Optional[Callable[[str], None]] = None,
        on_account_info: Optional[Callable[[str], None]] = None
    ):
        """Inicia a captura e monitoramento passivo de publicações."""
        self.browser_manager.start(
            on_posts=on_posts_received,
            on_status=on_status_change,
            on_account_info=on_account_info
        )

    def stop(self):
        """Interrompe a captura."""
        self.browser_manager.stop()

    def refresh(self, feed: Optional[str] = None):
        """Solicita recarregamento da timeline (específica ou atual)."""
        self.browser_manager.reload_timeline(feed)

    def load_more(self):
        """Solicita rolagem para carregar mais publicações."""
        self.browser_manager.scroll_down()

    def switch_feed_tab(self, feed: str):
        """Comanda o navegador a alternar entre fluxos ('for_you', 'following', 'mentions', 'dms')."""
        self.browser_manager.switch_feed_tab(feed)

    def navigate_to(self, url: str):
        """Comanda o navegador a acessar uma URL específica."""
        self.browser_manager.navigate_to(url)
