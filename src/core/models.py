"""
Modelos de dados universais para o Accessible Timeline.
Projetados para serem agnósticos de plataforma.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class MediaItem:
    """Representa uma mídia anexada a uma postagem."""
    media_type: str  # 'image', 'video', 'gif'
    url: str
    alt_text: Optional[str] = None


@dataclass
class Post:
    """Representa uma publicação de qualquer rede social suportada."""
    id: str
    platform: str
    author_name: str
    author_username: str
    text: str
    created_at: Optional[datetime] = None
    created_at_str: str = ""
    like_count: int = 0
    retweet_count: int = 0
    reply_count: int = 0
    media_items: List[MediaItem] = field(default_factory=list)
    url: str = ""
    is_retweet: bool = False
    retweeted_by: Optional[str] = None
    is_reply: bool = False
    replying_to: Optional[str] = None

    @property
    def has_media(self) -> bool:
        return len(self.media_items) > 0

    @property
    def media_summary(self) -> str:
        if not self.media_items:
            return ""
        count = len(self.media_items)
        types = [m.media_type for m in self.media_items]
        if all(t == "image" for t in types):
            return f"{count} imagem" if count == 1 else f"{count} imagens"
        elif any(t == "video" for t in types):
            return "vídeo"
        elif any(t == "gif" for t in types):
            return "GIF"
        return f"{count} mídias"

    def to_accessible_summary(self) -> str:
        """
        Retorna uma linha concisa para anúncio natural na lista pelo leitor de tela.
        Evita poluição sonora e destaca as informações fundamentais.
        """
        prefix = ""
        if self.is_retweet and self.retweeted_by:
            prefix = f"[Repost de {self.retweeted_by}] "
        elif self.is_reply and self.replying_to:
            prefix = f"[Respondendo a @{self.replying_to}] "

        time_part = f", {self.created_at_str}" if self.created_at_str else ""
        
        # Limpar quebras de linha no resumo de linha única para melhor leitura na lista
        clean_text = " ".join(self.text.split())
        if len(clean_text) > 160:
            clean_text = clean_text[:157] + "..."

        metrics = []
        if self.like_count > 0:
            metrics.append(f"{self.like_count} curtida" if self.like_count == 1 else f"{self.like_count} curtidas")
        if self.retweet_count > 0:
            metrics.append(f"{self.retweet_count} repost" if self.retweet_count == 1 else f"{self.retweet_count} reposts")
        if self.reply_count > 0:
            metrics.append(f"{self.reply_count} resposta" if self.reply_count == 1 else f"{self.reply_count} respostas")
        if self.has_media:
            metrics.append(self.media_summary)

        metrics_part = f" • {', '.join(metrics)}" if metrics else ""

        return f"{prefix}{self.author_name} (@{self.author_username}){time_part}: {clean_text}{metrics_part}"

    def to_accessible_full(self) -> str:
        """
        Retorna a publicação formatada em detalhes para diálogo ou leitura completa.
        """
        lines = []
        if self.is_retweet and self.retweeted_by:
            lines.append(f"Repostado por: {self.retweeted_by}")
        if self.is_reply and self.replying_to:
            lines.append(f"Em resposta a: @{self.replying_to}")

        lines.append(f"Autor: {self.author_name} (@{self.author_username})")
        if self.created_at_str:
            lines.append(f"Data/Hora: {self.created_at_str}")
        lines.append("")
        lines.append(self.text)
        lines.append("")

        metrics = []
        metrics.append(f"Curtidas: {self.like_count}")
        metrics.append(f"Repostagens: {self.retweet_count}")
        metrics.append(f"Respostas: {self.reply_count}")
        if self.has_media:
            metrics.append(f"Anexos: {self.media_summary}")
            for idx, media in enumerate(self.media_items, 1):
                alt = f" (Descrição: {media.alt_text})" if media.alt_text else ""
                lines.append(f"- Anexo {idx} [{media.media_type}]: {media.url}{alt}")
        lines.append(" | ".join(metrics))

        if self.url:
            lines.append(f"Link: {self.url}")

        return "\n".join(lines)
