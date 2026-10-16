import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from src.platforms.x_twitter.browser import setup_embedded_browsers_path, XBrowserManager


class TestBrowserSetup(unittest.TestCase):
    def setUp(self):
        self._orig_env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")

    def tearDown(self):
        if self._orig_env is not None:
            os.environ["PLAYWRIGHT_BROWSERS_PATH"] = self._orig_env
        else:
            os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)

    def test_setup_keeps_existing_env(self):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "custom_path"
        setup_embedded_browsers_path()
        self.assertEqual(os.environ["PLAYWRIGHT_BROWSERS_PATH"], "custom_path")

    @patch.object(sys, "frozen", True, create=True)
    @patch.object(sys, "executable", "C:/App/AccessibleTimeline.exe")
    @patch("src.platforms.x_twitter.browser.Path.exists")
    def test_setup_detects_frozen_embedded_browsers(self, mock_exists):
        os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)
        mock_exists.return_value = True

        setup_embedded_browsers_path()
        expected = str(Path("C:/App/browsers"))
        self.assertEqual(os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), expected)

    def test_launch_context_prioritizes_embedded_channel_none(self):
        manager = XBrowserManager(data_dir="test_data_dir")
        mock_pw = MagicMock()
        mock_context = MagicMock()
        mock_pw.chromium.launch_persistent_context.return_value = mock_context

        ctx = manager._launch_persistent_context_with_fallback(mock_pw, headless=True)
        self.assertEqual(ctx, mock_context)

        # Verifica se o primeiro canal tentado foi channel=None (sem argumento 'channel' em kwargs)
        first_call = mock_pw.chromium.launch_persistent_context.call_args_list[0]
        self.assertNotIn("channel", first_call.kwargs)
        self.assertTrue(first_call.kwargs["headless"])


if __name__ == "__main__":
    unittest.main()
