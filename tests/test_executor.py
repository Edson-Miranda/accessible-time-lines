import unittest
from unittest.mock import MagicMock
from src.platforms.x_twitter.executor import XActionExecutor


class TestXActionExecutor(unittest.TestCase):
    def setUp(self):
        self.mock_browser = MagicMock()
        self.executor = XActionExecutor(browser_manager=self.mock_browser)

    def test_create_post(self):
        self.mock_browser.execute_action.return_value = True
        result = self.executor.create_post("Olá mundo!")
        self.assertTrue(result)
        self.mock_browser.execute_action.assert_called_once_with("create_post", text="Olá mundo!")

    def test_reply_to_post(self):
        self.mock_browser.execute_action.return_value = True
        result = self.executor.reply_to_post("12345", "Minha resposta", author_username="fulano")
        self.assertTrue(result)
        self.mock_browser.execute_action.assert_called_once_with(
            "reply_to_post", post_id="12345", text="Minha resposta", author_username="fulano"
        )

    def test_retweet_post(self):
        self.mock_browser.execute_action.return_value = True
        result = self.executor.retweet_post("12345")
        self.assertTrue(result)
        self.mock_browser.execute_action.assert_called_once_with("retweet_post", post_id="12345")

    def test_quote_post(self):
        self.mock_browser.execute_action.return_value = True
        result = self.executor.quote_post("12345", "Comentário sobre o tweet", tweet_url="https://x.com/a/status/12345")
        self.assertTrue(result)
        self.mock_browser.execute_action.assert_called_once_with(
            "quote_post", post_id="12345", text="Comentário sobre o tweet", tweet_url="https://x.com/a/status/12345"
        )

    def test_like_post(self):
        self.mock_browser.execute_action.return_value = True
        result = self.executor.like_post("999")
        self.assertTrue(result)
        self.mock_browser.execute_action.assert_called_once_with("like_post", post_id="999")

    def test_unlike_post(self):
        self.mock_browser.execute_action.return_value = True
        result = self.executor.unlike_post("999")
        self.assertTrue(result)
        self.mock_browser.execute_action.assert_called_once_with("unlike_post", post_id="999")

    def test_send_dm(self):
        self.mock_browser.execute_action.return_value = True
        result = self.executor.send_dm("usuario_destino", "Olá via DM!")
        self.assertTrue(result)
        self.mock_browser.execute_action.assert_called_once_with(
            "send_dm", recipient="usuario_destino", text="Olá via DM!"
        )


if __name__ == "__main__":
    unittest.main()
