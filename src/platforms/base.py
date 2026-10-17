"""
Interfaces base abstratas para plataformas do Accessible Timeline.
Garante a separação estrita entre obtenção de dados e execução de ações.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional
from src.core.models import Post, User


class BaseTimelineReader(ABC):
    """
    Componente responsável exclusivamente por escutar, obter e converter
    publicações da plataforma em objetos Post universais.
    Não executa ações de escrita ou interação.
    """
    @abstractmethod
    def start(
        self,
        on_posts_received: Callable[[str, List[Post]], None],
        on_status_change: Optional[Callable[[str], None]] = None,
        on_account_info: Optional[Callable[[str], None]] = None
    ):
        """
        Inicia a observação da timeline.
        on_posts_received recebe (feed_type: str, posts: List[Post]).
        on_account_info recebe o nome/identificador da conta conectada.
        """
        pass

    @abstractmethod
    def stop(self):
        """Interrompe a observação da timeline."""
        pass

    @abstractmethod
    def refresh(self, feed: Optional[str] = None):
        """Solicita uma atualização manual da timeline."""
        pass

    @abstractmethod
    def switch_feed_tab(self, feed: str):
        """Alterna a guia/fluxo ativo no navegador ('for_you', 'following', etc.)."""
        pass

    @abstractmethod
    def navigate_to(self, url: str):
        """Navega para uma URL específica da plataforma."""
        pass


class BaseActionExecutor(ABC):
    """
    Componente responsável exclusivamente por executar ações no serviço
    (publicar, responder, repostar, citar, curtir, descurtir, enviar DM).
    Completamente desacoplado do leitor de timeline.
    """
    @abstractmethod
    def create_post(self, text: str) -> bool:
        """Publica um novo post/tweet."""
        pass

    @abstractmethod
    def reply_to_post(self, post_id: str, text: str, author_username: str = "") -> bool:
        """Envia uma resposta a uma publicação existente."""
        pass

    @abstractmethod
    def retweet_post(self, post_id: str) -> bool:
        """Reposta (retweet simples) uma publicação."""
        pass

    @abstractmethod
    def quote_post(self, post_id: str, text: str, tweet_url: str = "") -> bool:
        """Reposta com comentário (citar tweet)."""
        pass

    @abstractmethod
    def like_post(self, post_id: str) -> bool:
        """Curte uma publicação."""
        pass

    @abstractmethod
    def unlike_post(self, post_id: str) -> bool:
        """Remove a curtida (descurtir) de uma publicação."""
        pass

    @abstractmethod
    def send_dm(self, recipient_username: str, text: str) -> bool:
        """Envia uma mensagem direta (DM) privada para um usuário."""
        pass

    @abstractmethod
    def follow_user(self, username: str) -> bool:
        """Começa a seguir um usuário no serviço."""
        pass

    @abstractmethod
    def unfollow_user(self, username: str) -> bool:
        """Deixa de seguir um usuário no serviço."""
        pass

    @abstractmethod
    def block_user(self, username: str) -> bool:
        """Bloqueia um usuário no serviço."""
        pass

    @abstractmethod
    def unblock_user(self, username: str) -> bool:
        """Desbloqueia um usuário no serviço."""
        pass

    @abstractmethod
    def search_users(self, query: str) -> List[User]:
        """Pesquisa perfis de usuários na plataforma."""
        pass

    @abstractmethod
    def fetch_user_timeline(self, username: str) -> List[Post]:
        """Obtém as publicações recentes da linha do tempo de um usuário específico."""
        pass
