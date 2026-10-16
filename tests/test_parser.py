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

    def test_parse_modern_graphql_with_core_user(self):
        # Novo formato onde name e screen_name estão em user_results.result.core
        payload = {
            "data": {
                "home": {
                    "home_timeline_ux": {
                        "timeline": {
                            "instructions": [
                                {
                                    "type": "TimelineAddEntries",
                                    "entries": [
                                        {
                                            "entryId": "tweet-999999",
                                            "content": {
                                                "entryType": "TimelineTimelineItem",
                                                "itemContent": {
                                                    "itemType": "TimelineTweet",
                                                    "tweet_results": {
                                                        "result": {
                                                            "__typename": "Tweet",
                                                            "rest_id": "999999",
                                                            "core": {
                                                                "user_results": {
                                                                    "result": {
                                                                        "__typename": "User",
                                                                        "core": {
                                                                            "name": "Canaltech",
                                                                            "screen_name": "canaltech"
                                                                        }
                                                                    }
                                                                }
                                                            },
                                                            "legacy": {
                                                                "created_at": "Wed Oct 14 10:00:00 +0000 2026",
                                                                "full_text": "Notícia recente sobre tecnologia.",
                                                                "favorite_count": 100,
                                                                "retweet_count": 20
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

        posts = parse_x_graphql_response(payload)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].author_name, "Canaltech")
        self.assertEqual(posts[0].author_username, "canaltech")

    def test_post_full_text_not_truncated_in_summary(self):
        from src.core.models import Post
        long_text = (
            "Este é um texto consideravelmente longo com mais de duzentos caracteres para garantir que "
            "o leitor de tela (NVDA e JAWS) consiga ler toda a publicação diretamente ao navegar na "
            "lista pelas setas para cima e para baixo, sem que o texto seja interrompido abruptamente "
            "em cento e sessenta caracteres."
        )
        post = Post(
            id="123",
            platform="x_twitter",
            author_name="Acessibilidade Brasil",
            author_username="acessibilidade",
            text=long_text,
            like_count=10
        )
        summary = post.to_accessible_summary()
        # O resumo deve conter todo o texto longo, sem truncar com '...'
        self.assertIn("em cento e sessenta caracteres.", summary)
        self.assertNotIn("...", summary)

    def test_post_get_all_links(self):
        from src.core.models import Post, MediaItem
        post = Post(
            id="456",
            platform="x_twitter",
            author_name="Tech News",
            author_username="technews",
            text="Confira https://exemplo.com/materia e também https://outro.com/artigo!",
            urls=["https://exemplo.com/materia"],
            media_items=[MediaItem(media_type="image", url="https://pbs.twimg.com/media/foto.jpg")],
            url="https://x.com/technews/status/456"
        )
        links = post.get_all_links()
        self.assertIn("https://exemplo.com/materia", links)
        self.assertIn("https://outro.com/artigo", links)
        self.assertIn("https://pbs.twimg.com/media/foto.jpg", links)
        self.assertIn("https://x.com/technews/status/456", links)
        # Deve ter 4 links únicos
        self.assertEqual(len(links), 4)

    def test_parse_global_objects_notifications(self):
        payload = {
            "globalObjects": {
                "tweets": {
                    "888123": {
                        "id_str": "888123",
                        "full_text": "Você foi mencionado aqui https://t.co/xyz",
                        "user_id_str": "555",
                        "favorite_count": 5,
                        "entities": {
                            "urls": [
                                {
                                    "url": "https://t.co/xyz",
                                    "expanded_url": "https://noticia.com/alvo"
                                }
                            ]
                        }
                    }
                },
                "users": {
                    "555": {
                        "name": "Amigo Dev",
                        "screen_name": "amigodev"
                    }
                }
            }
        }
        posts = parse_x_graphql_response(payload)
        self.assertEqual(len(posts), 1)
        p = posts[0]
        self.assertEqual(p.id, "888123")
        self.assertEqual(p.author_name, "Amigo Dev")
        self.assertEqual(p.author_username, "amigodev")
        self.assertIn("https://noticia.com/alvo", p.urls)


if __name__ == "__main__":
    unittest.main()

