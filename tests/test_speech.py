import unittest
from unittest.mock import MagicMock, patch
from src.audio.speech import SpeechManager


class TestSpeechManager(unittest.TestCase):
    def setUp(self):
        self.speech = SpeechManager()

    def test_initial_state(self):
        self.assertTrue(self.speech.enabled)

    def test_speak_when_disabled(self):
        self.speech.enabled = False
        with patch.object(self.speech, "_nvda_client", create=True) as mock_nvda, \
             patch.object(self.speech, "_output", create=True) as mock_output:
            self.speech.speak("Teste", interrupt=True)
            mock_nvda.nvdaController_speakText.assert_not_called()
            mock_output.speak.assert_not_called()

    def test_speak_nvda_direct(self):
        self.speech.enabled = True
        mock_nvda = MagicMock()
        mock_nvda.nvdaController_testIfRunning.return_value = 0
        self.speech._nvda_client = mock_nvda

        self.speech.speak("Mensagem importante", interrupt=True)
        mock_nvda.nvdaController_cancelSpeech.assert_called_once()
        mock_nvda.nvdaController_speakText.assert_called_once_with("Mensagem importante")

    def test_speak_fallback_ao2(self):
        self.speech.enabled = True
        self.speech._nvda_client = None
        mock_output = MagicMock()
        self.speech._output = mock_output

        self.speech.speak("Mensagem via AO2", interrupt=False)
        mock_output.speak.assert_called_once_with("Mensagem via AO2", interrupt=False)

    def test_silence(self):
        mock_nvda = MagicMock()
        self.speech._nvda_client = mock_nvda
        mock_output = MagicMock()
        self.speech._output = mock_output

        self.speech.silence()
        mock_nvda.nvdaController_cancelSpeech.assert_called_once()
        mock_output.silence.assert_called_once()


if __name__ == "__main__":
    unittest.main()
