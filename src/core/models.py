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


def format_relative_time(dt: Optional[datetime], now: Optional[datetime] = None) -> str:
    """
    Formata um datetime em tempo relativo amigável e acessível (estilo TWBlue):
    Exemplos:
    - 'agora há pouco' (< 45s)
    - '1 minuto atrás' / '5 minutos atrás'
    - '1 hora atrás' / '3 horas atrás'
    - 'ontem' (se 1 dia) / '4 dias atrás'
    - '1 semana atrás' / '2 semanas atrás'
    - '1 mês atrás' / '5 meses atrás'
    - '1 ano atrás' / '2 anos atrás'
    """
    if not dt:
        return ""

    if now is None:
        if dt.tzinfo is not None:
            now = datetime.now(dt.tzinfo)
        else:
            now = datetime.now()

    # Normaliza fuso horário caso um tenha e outro não
    if dt.tzinfo is not None and now.tzinfo is None:
        now = now.astimezone(dt.tzinfo)
    elif dt.tzinfo is None and now.tzinfo is not None:
        dt = dt.astimezone(now.tzinfo)

    diff_seconds = (now - dt).total_seconds()
    if diff_seconds < 45:
        return "agora há pouco"

    diff_minutes = int(diff_seconds / 60)
    if diff_minutes < 60:
        return f"{diff_minutes} minuto atrás" if diff_minutes == 1 else f"{diff_minutes} minutos atrás"

    diff_hours = int(diff_seconds / 3600)
    if diff_hours < 24:
        return f"{diff_hours} hora atrás" if diff_hours == 1 else f"{diff_hours} horas atrás"

    diff_days = int(diff_seconds / 86400)
    if diff_days < 7:
        if diff_days == 1:
            return "ontem"
        return f"{diff_days} dias atrás"

    diff_weeks = int(diff_days / 7)
    if diff_weeks < 5:
        return f"{diff_weeks} semana atrás" if diff_weeks == 1 else f"{diff_weeks} semanas atrás"

    diff_months = int(diff_days / 30)
    if diff_months < 12:
        return f"{diff_months} mês atrás" if diff_months == 1 else f"{diff_months} meses atrás"

    diff_years = int(diff_days / 365)
    return f"{diff_years} ano atrás" if diff_years == 1 else f"{diff_years} anos atrás"


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
    urls: List[str] = field(default_factory=list)
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

    def get_all_links(self) -> List[str]:
        """
        Retorna todos os links únicos associados à publicação:
        links contidos nas entidades/texto, mídias e a URL da própria postagem.
        """
        links: List[str] = []

        # 1. URLs das entidades extraídas do tweet
        for u in self.urls:
            if u and u not in links:
                links.append(u)

        # 2. URLs detectadas no texto da postagem
        import re
        url_pattern = re.compile(r'https?://[^\s<>"\'()]+')
        for match in url_pattern.findall(self.text):
            clean = match.rstrip(".,;:!?")
            if clean and clean not in links:
                links.append(clean)

        # 3. URLs das mídias anexadas
        for m in self.media_items:
            if m.url and m.url not in links:
                links.append(m.url)

        # 4. URL da publicação no X
        if self.url and self.url not in links:
            links.append(self.url)

        return links

    def get_relative_time(self, now: Optional[datetime] = None) -> str:
        """Retorna o tempo decorrido desde a publicação em formato amigável."""
        if self.created_at:
            return format_relative_time(self.created_at, now=now)
        return self.created_at_str

    def to_accessible_summary(self) -> str:
        """
        Retorna o texto da publicação para anúncio natural na lista pelo leitor de tela.
        Lê o post completo sem truncar, normalizando quebras de linha em espaços.
        Exibe tempo relativo amigável no estilo TWBlue (ex.: '2 horas atrás', '3 semanas atrás').
        """
        prefix = ""
        if self.is_retweet and self.retweeted_by:
            prefix = f"[Repost de {self.retweeted_by}] "
        elif self.is_reply and self.replying_to:
            prefix = f"[Respondendo a @{self.replying_to}] "

        rel_time = self.get_relative_time()
        time_part = f", {rel_time}" if rel_time else ""
        
        # Normalizar quebras de linha em espaços para leitura contínua e fluida pelo leitor de tela
        clean_text = " ".join(self.text.split())

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
        rel_time = self.get_relative_time()
        if rel_time and self.created_at_str:
            lines.append(f"Data: {rel_time} ({self.created_at_str})")
        elif rel_time:
            lines.append(f"Data: {rel_time}")
        elif self.created_at_str:
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
