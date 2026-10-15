"""
Aplicação wxPython do Accessible Timeline.
Orquestra o ciclo de vida do aplicativo, da interface e do leitor de timeline,
distribuindo as postagens entre os stores 'Para você' e 'Seguindo'.
"""

import logging
from typing import List
import wx
from src.core.models import Post
from src.core.timeline_store import TimelineStore
from src.platforms.x_twitter.reader import XTimelineReader
from src.ui.main_window import MainWindow

logger = logging.getLogger("AccessibleTimeline.App")


class AccessibleTimelineApp(wx.App):
    def OnInit(self):
        self.SetAppName("Accessible Timeline")

        self.for_you_store = TimelineStore()
        self.following_store = TimelineStore()
        self.reader = XTimelineReader()

        # Cria a janela principal com os stores independentes
        self.main_window = MainWindow(
            for_you_store=self.for_you_store,
            following_store=self.following_store,
            reader=self.reader
        )
        self.SetTopWindow(self.main_window)
        self.main_window.Show()

        # Roteamento de postagens por feed
        def on_posts_received(feed_type: str, posts: List[Post]):
            if feed_type == "following":
                added = self.following_store.add_posts(posts, prepend=True)
                if added > 0:
                    logger.info(f"{added} novas postagens adicionadas à guia Seguindo.")
            else:
                added = self.for_you_store.add_posts(posts, prepend=True)
                if added > 0:
                    logger.info(f"{added} novas postagens adicionadas à guia Para você.")

        def on_status_change(status_text: str):
            self.main_window.set_status_message(status_text)

        # Inicia o leitor em thread de segundo plano
        self.reader.start(
            on_posts_received=on_posts_received,
            on_status_change=on_status_change
        )

        return True

    def OnExit(self):
        try:
            self.reader.stop()
        except Exception as e:
            logger.error(f"Erro ao finalizar: {e}")
        return super().OnExit()
