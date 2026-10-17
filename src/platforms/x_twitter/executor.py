"""
Executor de ações no X (Twitter).
Implementa BaseActionExecutor, isolando completamente a realização de ações
(publicar, responder, repostar, citar, curtir, descurtir e enviar DM).
Totalmente desacoplado do leitor e do parser de timelines.
"""

import logging
import threading
from typing import Callable, List, Optional
import wx
from src.core.models import Post, User
from src.platforms.base import BaseActionExecutor
from src.platforms.x_twitter.browser import XBrowserManager

logger = logging.getLogger("AccessibleTimeline.ActionExecutor")


class XActionExecutor(BaseActionExecutor):
    """
    Controlador de execução de ações do usuário no X através do navegador persistente.
    Oferece execução síncrona e despacho assíncrono para garantir fluidez na interface gráfica.
    """
    def __init__(self, browser_manager: Optional[XBrowserManager] = None):
        self.browser_manager = browser_manager or XBrowserManager()

    def create_post(self, text: str) -> bool:
        """Publica um novo post/tweet."""
        return self.browser_manager.execute_action("create_post", text=text)

    def reply_to_post(self, post_id: str, text: str, author_username: str = "") -> bool:
        """Envia uma resposta a uma publicação existente."""
        return self.browser_manager.execute_action("reply_to_post", post_id=post_id, text=text, author_username=author_username)

    def retweet_post(self, post_id: str) -> bool:
        """Reposta (retweet simples) uma publicação."""
        return self.browser_manager.execute_action("retweet_post", post_id=post_id)

    def quote_post(self, post_id: str, text: str, tweet_url: str = "") -> bool:
        """Reposta com comentário (citar tweet)."""
        return self.browser_manager.execute_action("quote_post", post_id=post_id, text=text, tweet_url=tweet_url)

    def like_post(self, post_id: str) -> bool:
        """Curte uma publicação."""
        return self.browser_manager.execute_action("like_post", post_id=post_id)

    def unlike_post(self, post_id: str) -> bool:
        """Remove a curtida (descurtir) de uma publicação."""
        return self.browser_manager.execute_action("unlike_post", post_id=post_id)

    def send_dm(self, recipient_username: str, text: str) -> bool:
        """Envia uma mensagem direta (DM) privada para um usuário."""
        return self.browser_manager.execute_action("send_dm", recipient=recipient_username, text=text)

    def follow_user(self, username: str) -> bool:
        """Começa a seguir um usuário no serviço."""
        return bool(self.browser_manager.execute_action("follow_user", username=username))

    def unfollow_user(self, username: str) -> bool:
        """Deixa de seguir um usuário no serviço."""
        return bool(self.browser_manager.execute_action("unfollow_user", username=username))

    def block_user(self, username: str) -> bool:
        """Bloqueia um usuário no serviço."""
        return bool(self.browser_manager.execute_action("block_user", username=username))

    def unblock_user(self, username: str) -> bool:
        """Desbloqueia um usuário no serviço."""
        return bool(self.browser_manager.execute_action("unblock_user", username=username))

    def search_users(self, query: str) -> List[User]:
        """Pesquisa perfis de usuários na plataforma."""
        res = self.browser_manager.execute_action("search_users", query=query)
        return res if isinstance(res, list) else []

    def fetch_user_timeline(self, username: str) -> List[Post]:
        """Obtém as publicações recentes da linha do tempo de um usuário específico."""
        res = self.browser_manager.execute_action("fetch_user_timeline", username=username)
        return res if isinstance(res, list) else []

    def run_async(
        self,
        action_fn: Callable[[], bool],
        on_success: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[], None]] = None
    ):
        """
        Executa uma ação em thread dedicada de segundo plano sem bloquear a interface wxPython,
        despachando os callbacks de conclusão na thread principal de UI via wx.CallAfter.
        """
        def _worker():
            try:
                success = action_fn()
                if success:
                    if on_success:
                        wx.CallAfter(on_success)
                else:
                    if on_error:
                        wx.CallAfter(on_error)
            except Exception as e:
                logger.error(f"Erro assíncrono ao executar ação: {e}")
                if on_error:
                    wx.CallAfter(on_error)

        t = threading.Thread(target=_worker, daemon=True, name="ActionExecutorWorker")
        t.start()
