import unittest
from src.platforms.x_twitter.parser import parse_x_graphql_response


class TestXParser(unittest.TestCase):
    def test_parse_sample_graphql(self):
        sample_payload = {
            "data": {
                "home": {
                    "home_timeline_ux": {
                        "timeline": {
                            "instructions": [
                                {
                                    "type": "TimelineAddEntries",
                                    "entries": [
                                        {
                                            "entryId": "tweet-1845123456789",
                                            "content": {
                                                "entryType": "TimelineTimelineItem",
                                                "itemContent": {
                                                    "itemType": "TimelineTweet",
                                                    "tweet_results": {
                                                        "result": {
                                                            "__typename": "Tweet",
                                                            "rest_id": "1845123456789",
                                                            "core": {
                                                                "user_results": {
                                                                    "result": {
                                                                        "__typename": "User",
                                                                        "legacy": {
                                                                            "name": "Maria Silva",
                                                                            "screen_name": "mariasilva"
                                                                        }
                                                                    }
                                                                }
                                                            },
                                                            "legacy": {
                                                                "created_at": "Mon Oct 12 18:30:00 +0000 2026",
                                                                "full_text": "Olá mundo! Testando o Accessible Timeline no X.",
                                                                "favorite_count": 42,
                                                                "retweet_count": 5,
                                                                "reply_count": 3,
                                                                "entities": {
                                                                    "media": [
                                                                        {
                                                                            "type": "photo",
                                                                            "media_url_https": "https://pbs.twimg.com/media/test.jpg",
                                                                            "ext_alt_text": "Captura de tela do aplicativo"
                                                                        }
                                                                    ]
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                }
            }
        }

        posts = parse_x_graphql_response(sample_payload)
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertEqual(post.id, "1845123456789")
        self.assertEqual(post.author_name, "Maria Silva")
        self.assertEqual(post.author_username, "mariasilva")
        self.assertEqual(post.like_count, 42)
        self.assertEqual(post.retweet_count, 5)
        self.assertEqual(post.reply_count, 3)
        self.assertTrue(post.has_media)
        self.assertEqual(post.media_items[0].alt_text, "Captura de tela do aplicativo")
        
        # Test accessible summary
        summary = post.to_accessible_summary()
        self.assertIn("Maria Silva (@mariasilva)", summary)
        self.assertIn("Olá mundo!", summary)
        self.assertIn("42 curtidas", summary)
        self.assertIn("5 reposts", summary)
        self.assertIn("1 imagem", summary)


if __name__ == "__main__":
    unittest.main()
