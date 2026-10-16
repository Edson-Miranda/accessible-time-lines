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

    def test_chronological_ordering_newest_at_top(self):
        from datetime import datetime, timezone, timedelta

        base_time = datetime(2026, 10, 16, 15, 0, 0, tzinfo=timezone.utc)
        p_mid = Post(
            id="100", platform="x", author_name="Mid", author_username="mid", text="Meio",
            created_at=base_time
        )
        p_old = Post(
            id="90", platform="x", author_name="Old", author_username="old", text="Antigo",
            created_at=base_time - timedelta(hours=2)
        )
        p_new = Post(
            id="110", platform="x", author_name="New", author_username="new", text="Novo",
            created_at=base_time + timedelta(hours=1)
        )

        # Adiciona fora de ordem
        self.store.add_posts([p_old, p_mid, p_new])
        self.assertEqual(self.store.count(), 3)

        # O mais recente (p_new) deve estar no topo (índice 0)
        self.assertEqual(self.store.get_post(0).id, "110")
        self.assertEqual(self.store.get_post(1).id, "100")
        self.assertEqual(self.store.get_post(2).id, "90")

        # Adiciona post ainda mais recente (p_latest)
        p_latest = Post(
            id="120", platform="x", author_name="Latest", author_username="latest", text="Novíssimo",
            created_at=base_time + timedelta(hours=3)
        )
        self.store.add_posts([p_latest])
        self.assertEqual(self.store.get_post(0).id, "120")

        # Adiciona post mais antigo ainda (p_ancient)
        p_ancient = Post(
            id="50", platform="x", author_name="Ancient", author_username="ancient", text="Mais antigo",
            created_at=base_time - timedelta(days=2)
        )
        self.store.add_posts([p_ancient])
        self.assertEqual(self.store.get_post(4).id, "50")

    def test_format_relative_time(self):
        from datetime import datetime, timezone, timedelta
        from src.core.models import format_relative_time

        ref_now = datetime(2026, 10, 16, 18, 0, 0, tzinfo=timezone.utc)

        # 30 segundos atrás
        dt = ref_now - timedelta(seconds=30)
        self.assertEqual(format_relative_time(dt, now=ref_now), "agora há pouco")

        # 1 minuto atrás
        dt = ref_now - timedelta(minutes=1, seconds=10)
        self.assertEqual(format_relative_time(dt, now=ref_now), "1 minuto atrás")

        # 15 minutos atrás
        dt = ref_now - timedelta(minutes=15)
        self.assertEqual(format_relative_time(dt, now=ref_now), "15 minutos atrás")

        # 1 hora atrás
        dt = ref_now - timedelta(hours=1)
        self.assertEqual(format_relative_time(dt, now=ref_now), "1 hora atrás")

        # 3 horas atrás
        dt = ref_now - timedelta(hours=3)
        self.assertEqual(format_relative_time(dt, now=ref_now), "3 horas atrás")

        # Ontem (1 dia)
        dt = ref_now - timedelta(days=1)
        self.assertEqual(format_relative_time(dt, now=ref_now), "ontem")

        # 4 dias atrás
        dt = ref_now - timedelta(days=4)
        self.assertEqual(format_relative_time(dt, now=ref_now), "4 dias atrás")

        # 2 semanas atrás
        dt = ref_now - timedelta(weeks=2)
        self.assertEqual(format_relative_time(dt, now=ref_now), "2 semanas atrás")

        # 3 meses atrás
        dt = ref_now - timedelta(days=95)
        self.assertEqual(format_relative_time(dt, now=ref_now), "3 meses atrás")

        # 1 ano atrás
        dt = ref_now - timedelta(days=380)
        self.assertEqual(format_relative_time(dt, now=ref_now), "1 ano atrás")


if __name__ == "__main__":
    unittest.main()
