"""
Gerenciador de saída de voz e suporte a leitores de tela para o Accessible Timeline.
Utiliza accessible_output2 com detecção automática de NVDA, JAWS e SAPI,
além de carregar diretamente as bibliotecas locais do NVDA Controller Client.
"""

import ctypes
import logging
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger("AccessibleTimeline.Speech")

# Garante que o diretório de DLLs do projeto esteja no PATH de busca de DLLs
def _setup_dll_directory():
    try:
        base_dir = Path(__file__).resolve().parent / "lib" / "x64"
        if base_dir.exists():
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(str(base_dir))
            os.environ["PATH"] = str(base_dir) + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        logger.debug(f"Aviso ao registrar diretório de DLLs de áudio/voz: {e}")

_setup_dll_directory()


class SpeechManager:
    """
    Controlador central de fala e anúncios para leitores de tela.
    Totalmente thread-safe e tolerante a falhas.
    """
    def __init__(self):
        self._output = None
        self._nvda_client = None
        self.enabled = True
        self._init_output()

    def _init_output(self):
        """Inicializa a biblioteca de saída acessível com fallbacks adequados."""
        # 1. Tenta carregar DLL nativa local do NVDA
        try:
            dll_path = Path(__file__).resolve().parent / "lib" / "x64" / "nvdaControllerClient.dll"
            if dll_path.exists():
                self._nvda_client = ctypes.windll.LoadLibrary(str(dll_path))
                logger.info("NVDA Controller Client nativo carregado com sucesso.")
        except Exception as e:
            logger.debug(f"Aviso ao carregar nvdaControllerClient local: {e}")

        # 2. Inicializa accessible_output2 para suporte universal (NVDA, JAWS, Dolphin, SAPI5)
        try:
            import accessible_output2.outputs.auto
            self._output = accessible_output2.outputs.auto.Auto()
            active_name = self.get_active_screen_reader_name()
            logger.info(f"Sistema de voz acessível inicializado. Saída ativa: {active_name}")
        except Exception as e:
            logger.warning(f"Erro ao inicializar accessible_output2: {e}")

    def get_active_screen_reader_name(self) -> str:
        """Retorna o nome do sintetizador ou leitor de tela atualmente ativo."""
        try:
            if self._output and hasattr(self._output, "output"):
                out = self._output.output
                if callable(out):
                    out = out()
                if out and hasattr(out, "name"):
                    return str(out.name)
        except Exception:
            pass
        return "Sintetizador Padrão"

    def speak(self, text: str, interrupt: bool = False):
        """
        Envia uma cadeia de texto para leitura pelo sintetizador/leitor de tela ativo.
        """
        if not self.enabled or not text:
            return

        clean_text = " ".join(str(text).split())
        if not clean_text:
            return

        # 1. Tenta fala direta via NVDA Controller Client nativo se ativo
        spoken_via_nvda = False
        if self._nvda_client:
            try:
                if self._nvda_client.nvdaController_testIfRunning() == 0:
                    if interrupt:
                        self._nvda_client.nvdaController_cancelSpeech()
                    self._nvda_client.nvdaController_speakText(clean_text)
                    spoken_via_nvda = True
            except Exception as e:
                logger.debug(f"Aviso na fala direta do NVDA: {e}")

        # 2. Se não falou via NVDA direto, despacha para accessible_output2 (suporta JAWS, SAPI, etc.)
        if not spoken_via_nvda and self._output:
            try:
                self._output.speak(clean_text, interrupt=interrupt)
            except Exception as e:
                logger.debug(f"Aviso ao falar via accessible_output2: {e}")

    def silence(self):
        """Interrompe qualquer fala em andamento."""
        if self._nvda_client:
            try:
                self._nvda_client.nvdaController_cancelSpeech()
            except Exception:
                pass
        if self._output and hasattr(self._output, "silence"):
            try:
                self._output.silence()
            except Exception:
                pass


# Instância global compartilhada
speech_manager = SpeechManager()
