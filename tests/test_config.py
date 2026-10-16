import json
import os
import tempfile
import unittest
from pathlib import Path

from src.core.config import ConfigManager, DEFAULT_CONFIG


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = Path(self.temp_dir.name) / "test_config.json"
        # Cria uma instância isolada para teste
        self.manager = ConfigManager.__new__(ConfigManager)
        self.manager._initialized = False
        self.manager.__init__(config_file=str(self.config_file))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_values(self):
        self.assertTrue(self.manager.get("check_updates_automatically"))
        self.assertTrue(self.manager.get("sound_enabled"))
        self.assertEqual(self.manager.get("sound_theme"), "default")

    def test_set_and_get(self):
        self.manager.set("check_updates_automatically", False)
        self.assertFalse(self.manager.get("check_updates_automatically"))

        # Verifica se gravou no arquivo físico
        self.assertTrue(self.config_file.exists())
        with open(self.config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertFalse(data.get("check_updates_automatically"))

    def test_load_existing_file(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump({"check_updates_automatically": False, "sound_theme": "classic"}, f)

        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        mgr.__init__(config_file=str(self.config_file))

        self.assertFalse(mgr.get("check_updates_automatically"))
        self.assertEqual(mgr.get("sound_theme"), "classic")
        # Mantém padrão para chaves ausentes
        self.assertTrue(mgr.get("sound_enabled"))

    def test_corrupted_file_recovery(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write("{invalid_json: 123")

        mgr = ConfigManager.__new__(ConfigManager)
        mgr._initialized = False
        mgr.__init__(config_file=str(self.config_file))

        # Restaura padrões sem crash
        self.assertTrue(mgr.get("check_updates_automatically"))


if __name__ == "__main__":
    unittest.main()
