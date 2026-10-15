"""
Gerenciador de estado e armazenamento em memória da timeline.
Garante thread-safety, deduplicação por ID e preservação da posição de leitura.
"""

import threading
from typing import Callable, Dict, List, Optional
from src.core.models import Post


class TimelineStore:
    def __init__(self):
        self._lock = threading.RLock()
        self._posts: List[Post] = []
        self._posts_by_id: Dict[str, Post] = {}
        self._current_index: int = -1
        self._current_post_id: Optional[str] = None
        self._listeners: List[Callable[[List[Post], int], None]] = []

    def subscribe(self, listener: Callable[[List[Post], int], None]):
        """Registra um callback para ser notificado quando a timeline mudar."""
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[List[Post], int], None]):
        """Remove um callback registrado."""
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _notify(self):
        """Notifica todos os ouvintes sobre alterações."""
        posts_copy = list(self._posts)
        idx = self._current_index
        for listener in self._listeners:
            try:
                listener(posts_copy, idx)
            except Exception as e:
                print(f"[TimelineStore] Erro ao notificar ouvinte: {e}")

    def add_posts(self, incoming_posts: List[Post], prepend: bool = True) -> int:
        """
        Adiciona postagens à lista, descartando duplicatas e preservando a posição de leitura.
        Retorna a quantidade de novas postagens adicionadas.
        """
        with self._lock:
            added_count = 0
            new_items: List[Post] = []

            for post in incoming_posts:
                if post.id in self._posts_by_id:
                    # Atualiza métricas da postagem existente
                    existing = self._posts_by_id[post.id]
                    existing.like_count = post.like_count
                    existing.retweet_count = post.retweet_count
                    existing.reply_count = post.reply_count
                    continue

                self._posts_by_id[post.id] = post
                new_items.append(post)
                added_count += 1

            if not new_items:
                if added_count == 0 and incoming_posts:
                    # Pode ter havido atualização de métricas
                    self._notify()
                return 0

            # Guardar o ID do post atualmente selecionado para preservar a posição
            target_selected_id = self._current_post_id

            if prepend:
                self._posts = new_items + self._posts
            else:
                self._posts.extend(new_items)

            # Recalcular índice para preservar a posição de leitura
            if target_selected_id and target_selected_id in self._posts_by_id:
                for idx, p in enumerate(self._posts):
                    if p.id == target_selected_id:
                        self._current_index = idx
                        break
            else:
                if self._posts:
                    # Se não havia nada selecionado, seleciona o primeiro item
                    if self._current_index == -1:
                        self._current_index = 0
                        self._current_post_id = self._posts[0].id

            self._notify()
            return added_count

    def set_current_index(self, index: int) -> bool:
        """Define o índice atual de leitura e atualiza o post selecionado."""
        with self._lock:
            if not self._posts:
                self._current_index = -1
                self._current_post_id = None
                return False

            if 0 <= index < len(self._posts):
                self._current_index = index
                self._current_post_id = self._posts[index].id
                return True
            return False

    def get_current_index(self) -> int:
        with self._lock:
            return self._current_index

    def get_current_post(self) -> Optional[Post]:
        with self._lock:
            if 0 <= self._current_index < len(self._posts):
                return self._posts[self._current_index]
            return None

    def get_post(self, index: int) -> Optional[Post]:
        with self._lock:
            if 0 <= index < len(self._posts):
                return self._posts[index]
            return None

    def get_all_posts(self) -> List[Post]:
        with self._lock:
            return list(self._posts)

    def count(self) -> int:
        with self._lock:
            return len(self._posts)

    def clear(self):
        with self._lock:
            self._posts.clear()
            self._posts_by_id.clear()
            self._current_index = -1
            self._current_post_id = None
            self._notify()
