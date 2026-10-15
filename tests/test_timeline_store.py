import unittest
from src.core.models import Post
from src.core.timeline_store import TimelineStore


class TestTimelineStore(unittest.TestCase):
    def setUp(self):
        self.store = TimelineStore()

    def test_add_and_deduplicate(self):
        p1 = Post(id="1", platform="x", author_name="A", author_username="a", text="Texto 1")
        p2 = Post(id="2", platform="x", author_name="B", author_username="b", text="Texto 2")

        added = self.store.add_posts([p1, p2])
        self.assertEqual(added, 2)
        self.assertEqual(self.store.count(), 2)

        # Adicionar post repetido com curtidas alteradas
        p1_updated = Post(id="1", platform="x", author_name="A", author_username="a", text="Texto 1", like_count=10)
        added_repeat = self.store.add_posts([p1_updated])
        self.assertEqual(added_repeat, 0)
        self.assertEqual(self.store.count(), 2)
        self.assertEqual(self.store.get_post(0).like_count, 10)

    def test_reading_position_preservation(self):
        p1 = Post(id="1", platform="x", author_name="A", author_username="a", text="Primeiro")
        p2 = Post(id="2", platform="x", author_name="B", author_username="b", text="Segundo")
        self.store.add_posts([p1, p2])

        # Usuário seleciona o post 2 (índice 1)
        self.store.set_current_index(1)
        self.assertEqual(self.store.get_current_post().id, "2")

        # Chegam 2 novos posts mais recentes (prepended no topo)
        p3 = Post(id="3", platform="x", author_name="C", author_username="c", text="Terceiro")
        p4 = Post(id="4", platform="x", author_name="D", author_username="d", text="Quarto")
        self.store.add_posts([p3, p4], prepend=True)

        # O post "2" agora está no índice 3, mas deve continuar selecionado!
        self.assertEqual(self.store.get_current_post().id, "2")
        self.assertEqual(self.store.get_current_index(), 3)


if __name__ == "__main__":
    unittest.main()
