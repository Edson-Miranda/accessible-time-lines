"""
Interfaces base abstratas para plataformas do Accessible Timeline.
Garante a separação estrita entre obtenção de dados e execução de ações.
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional
from src.core.models import Post


class BaseTimelineReader(ABC):
    """
    Componente responsável exclusivamente por escutar, obter e converter
    publicações da plataforma em objetos Post universais.
    Não executa ações de escrita ou interação.
    """
    @abstractmethod
    def start(self, on_posts_received: Callable[[List[Post]], None], on_status_change: Optional[Callable[[str], None]] = None):
        """Inicia a observação da timeline."""
        pass

    @abstractmethod
    def stop(self):
        """Interrompe a observação da timeline."""
        pass

    @abstractmethod
    def refresh(self):
        """Solicita uma atualização manual da timeline."""
        pass


class BaseActionExecutor(ABC):
    """
    Componente responsável exclusivamente por executar ações no serviço
    (curtir, repostar, responder, publicar).
    Completamente desacoplado do leitor de timeline.
    """
    @abstractmethod
    def like_post(self, post_id: str) -> bool:
        pass

    @abstractmethod
    def retweet_post(self, post_id: str) -> bool:
        pass

    @abstractmethod
    def reply_to_post(self, post_id: str, text: str) -> bool:
        pass

    @abstractmethod
    def create_post(self, text: str) -> bool:
        pass
