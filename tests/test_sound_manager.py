import unittest
from pathlib import Path
from src.audio.manager import SoundManager, sound_manager


class TestSoundManager(unittest.TestCase):
    def setUp(self):
        self.manager = sound_manager
        self.original_theme = self.manager.theme_name
        self.original_enabled = self.manager.enabled

    def tearDown(self):
        self.manager.theme_name = self.original_theme
        self.manager.enabled = self.original_enabled

    def test_singleton(self):
        sm1 = SoundManager()
        sm2 = SoundManager()
        self.assertIs(sm1, sm2)
        self.assertIs(sm1, self.manager)

    def test_theme_switch(self):
        self.manager.set_theme("classic")
        self.assertEqual(self.manager.theme_name, "classic")
        self.manager.set_theme("default")
        self.assertEqual(self.manager.theme_name, "default")

    def test_resolve_sound_path_existing(self):
        # O arquivo ready.ogg existe no pacote default
        path = self.manager._resolve_sound_path("ready")
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "ready.ogg")

    def test_resolve_sound_path_with_extension(self):
        path = self.manager._resolve_sound_path("ready.ogg")
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

    def test_resolve_sound_path_theme_fallback(self):
        # Se um tema não possuir um som específico, ele deve fazer fallback para o default
        self.manager.set_theme("Qwitter")
        path = self.manager._resolve_sound_path("ready")
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

    def test_resolve_sound_path_nonexistent(self):
        path = self.manager._resolve_sound_path("som_inexistente_12345")
        self.assertIsNone(path)

    def test_sound_methods_non_blocking_execution(self):
        # Verifica se todas as chamadas semânticas executam sem erros
        self.manager.play_ready()
        self.manager.play_tweet_sent()
        self.manager.play_reply_sent()
        self.manager.play_retweet_sent()
        self.manager.play_favourite()
        self.manager.play_dm_sent()
        self.manager.play_tweet_received()
        self.manager.play_mention_received()
        self.manager.play_dm_received()
        self.manager.play_max_length()
        self.manager.play_error()

    def test_disabled_playback(self):
        self.manager.enabled = False
        # Não deve lançar erro nem tocar som
        self.manager.play("ready")
        self.assertFalse(self.manager.enabled)


if __name__ == "__main__":
    unittest.main()
