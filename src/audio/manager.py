"""
Gerenciador de reprodução sonora do Accessible Timeline.
Utiliza a biblioteca de áudio BASS (bass.dll) para reproduzir os sons nativos
dos pacotes sonoros do TWBlue (OGG Vorbis) com baixíssima latência e alta fidelidade.
"""

import ctypes
import logging
import os
from pathlib import Path
import threading
from typing import Dict, Optional

logger = logging.getLogger("AccessibleTimeline.Audio")

BASS_UNICODE = 0x80000000


class SoundManager:
    """
    Gerenciador singleton de efeitos sonoros de acessibilidade.
    Carrega bass.dll e executa sons de eventos baseados nos temas do TWBlue.
    """
    _instance: Optional["SoundManager"] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, theme_name: str = "default"):
        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self.theme_name = theme_name
        self.enabled = True
        self._bass: Optional[ctypes.CDLL] = None
        self._active_streams: Dict[str, int] = {}
        self._root_dir = Path(__file__).resolve().parent.parent.parent
        self._sounds_dir = self._root_dir / "sounds"

        self._init_bass()

    def _init_bass(self):
        """Localiza e inicializa a biblioteca BASS."""
        dll_candidates = [
            self._root_dir / "src" / "audio" / "lib" / "x64" / "bass.dll",
            self._root_dir / "lib" / "x64" / "bass.dll",
            Path(r"C:\Windows\System32\bass.dll"),
        ]

        dll_path = None
        for cand in dll_candidates:
            if cand.exists():
                dll_path = cand
                break

        if not dll_path:
            logger.warning("Biblioteca bass.dll não encontrada. O som estará desabilitado.")
            return

        try:
            self._bass = ctypes.cdll.LoadLibrary(str(dll_path))
            # BASS_Init(device=-1, freq=44100, flags=0, win=0, dsguid=None)
            res = self._bass.BASS_Init(-1, 44100, 0, 0, None)
            # Código de erro 37 significa BASS_ERROR_ALREADY (já inicializado)
            if not res and self._bass.BASS_ErrorGetCode() != 37:
                logger.warning(f"Falha ao inicializar dispositivo de áudio BASS: {self._bass.BASS_ErrorGetCode()}")
            else:
                logger.info(f"Sistema sonoro BASS inicializado com sucesso via {dll_path}")
        except Exception as e:
            logger.error(f"Erro ao carregar bass.dll: {e}")
            self._bass = None

    def set_theme(self, theme_name: str):
        """Altera o pacote de sons ativo (ex.: 'default', 'classic', 'Qwitter')."""
        self.theme_name = theme_name
        logger.info(f"Tema de som alterado para: {theme_name}")

    def _resolve_sound_path(self, sound_name: str) -> Optional[Path]:
        """Localiza o arquivo .ogg correspondente no tema atual ou no tema default."""
        base_name = sound_name if sound_name.endswith(".ogg") else f"{sound_name}.ogg"

        theme_path = self._sounds_dir / self.theme_name / base_name
        if theme_path.exists():
            return theme_path

        default_path = self._sounds_dir / "default" / base_name
        if default_path.exists():
            return default_path

        return None

    def play(self, sound_name: str):
        """Reproduz um som de evento de forma assíncrona e não bloqueante."""
        if not self.enabled or not self._bass:
            return

        def _play_worker():
            try:
                sound_file = self._resolve_sound_path(sound_name)
                if not sound_file:
                    logger.debug(f"Arquivo de som não encontrado: {sound_name}")
                    return

                # BASS_StreamCreateFile(mem=False, file=path, offset=0, length=0, flags=BASS_UNICODE)
                stream = self._bass.BASS_StreamCreateFile(False, str(sound_file), 0, 0, BASS_UNICODE)
                if stream:
                    self._bass.BASS_ChannelPlay(stream, True)
            except Exception as e:
                logger.debug(f"Erro ao reproduzir som {sound_name}: {e}")

        # Dispara em thread leve para nunca impactar o fluxo do evento
        threading.Thread(target=_play_worker, daemon=True, name=f"PlaySound_{sound_name}").start()

    # Atalhos semânticos para os principais eventos do Accessible Timeline
    def play_ready(self):
        """Som de sistema inicializado e pronto."""
        self.play("ready")

    def play_tweet_sent(self):
        """Som de publicação enviada com sucesso."""
        self.play("tweet_send")

    def play_reply_sent(self):
        """Som de resposta enviada com sucesso."""
        self.play("reply_send")

    def play_retweet_sent(self):
        """Som de repost/retweet realizado."""
        self.play("retweet_send")

    def play_favourite(self):
        """Som de publicação favoritada/curtida."""
        self.play("favourite")

    def play_dm_sent(self):
        """Som de mensagem direta (DM) enviada."""
        self.play("dm_sent")

    def play_tweet_received(self):
        """Som de novos tweets recebidos na timeline."""
        self.play("tweet_received")

    def play_mention_received(self):
        """Som de menção recebida."""
        self.play("mention_received")

    def play_dm_received(self):
        """Som de mensagem direta recebida."""
        self.play("dm_received")

    def play_max_length(self):
        """Som de aviso de limite de caracteres atingido."""
        self.play("max_length")

    def play_error(self):
        """Som de erro em operação."""
        self.play("error")

    def close(self):
        """Libera recursos do BASS no encerramento do aplicativo."""
        if self._bass:
            try:
                self._bass.BASS_Free()
            except Exception:
                pass


# Instância global compartilhada
sound_manager = SoundManager()
