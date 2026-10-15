"""
Janela principal do Accessible Timeline.
Utiliza controles nativos Win32 (wx.ListCtrl) garantindo compatibilidade total
com NVDA, JAWS e demais leitores de tela sem causar anúncios duplicados.
"""

import logging
from typing import List
import wx
from src.core.models import Post
from src.core.timeline_store import TimelineStore
from src.platforms.x_twitter.reader import XTimelineReader
from src.ui.dialogs import PostDetailsDialog

logger = logging.getLogger("AccessibleTimeline.MainWindow")


class MainWindow(wx.Frame):
    def __init__(self, store: TimelineStore, reader: XTimelineReader):
        super().__init__(
            parent=None,
            id=wx.ID_ANY,
            title="Accessible Timeline - X (Twitter)",
            size=(850, 600),
            style=wx.DEFAULT_FRAME_STYLE
        )

        self.store = store
        self.reader = reader
        self._updating_ui = False

        self._init_menu()
        self._init_ui()
        self._init_events()

        # Inscrição para receber atualizações da timeline
        self.store.subscribe(self._on_store_updated)

        self.Center()

    def _init_menu(self):
        menu_bar = wx.MenuBar()

        # Menu Timeline
        timeline_menu = wx.Menu()
        item_refresh = timeline_menu.Append(wx.ID_REFRESH, "&Atualizar Timeline\tF5", "Recarrega as postagens do X")
        item_load_more = timeline_menu.Append(wx.ID_ANY, "Carregar &Mais Postagens\tCtrl+M", "Solicita rolagem no navegador para mais postagens")
        timeline_menu.AppendSeparator()
        item_details = timeline_menu.Append(wx.ID_ANY, "Ver &Detalhes da Publicação\tEnter", "Abre os detalhes da postagem selecionada")
        timeline_menu.AppendSeparator()
        item_exit = timeline_menu.Append(wx.ID_EXIT, "Sai&r\tAlt+F4", "Fecha o Accessible Timeline")
        menu_bar.Append(timeline_menu, "&Timeline")

        # Menu Navegador
        browser_menu = wx.Menu()
        item_toggle_browser = browser_menu.Append(wx.ID_ANY, "Exibir/&Ocultar Janela do Navegador\tF11", "Exibe ou oculta a janela do Chromium para login ou verificações")
        menu_bar.Append(browser_menu, "&Navegador")

        # Menu Ajuda
        help_menu = wx.Menu()
        item_about = help_menu.Append(wx.ID_ABOUT, "&Sobre\tF1", "Informações sobre o aplicativo")
        menu_bar.Append(help_menu, "A&juda")

        self.SetMenuBar(menu_bar)

        # Binds de menus
        self.Bind(wx.EVT_MENU, self._on_refresh, item_refresh)
        self.Bind(wx.EVT_MENU, self._on_load_more, item_load_more)
        self.Bind(wx.EVT_MENU, self._on_open_details, item_details)
        self.Bind(wx.EVT_MENU, self._on_toggle_browser, item_toggle_browser)
        self.Bind(wx.EVT_MENU, self._on_about, item_about)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), item_exit)

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Rótulo de instrução acessível
        self.info_label = wx.StaticText(
            panel,
            label="Lista de publicações da Timeline. Use as setas Cima e Baixo para navegar, Enter para detalhes, F5 para atualizar e F11 para abrir o navegador de login:"
        )
        sizer.Add(self.info_label, 0, wx.ALL, 8)

        # Lista acessível nativa Win32 (SysListView32)
        # Modo relatório de 1 coluna sem cabeçalho visual para leitura direta pelo leitor de tela
        self.list_ctrl = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL
        )
        self.list_ctrl.InsertColumn(0, "Publicação", width=wx.LIST_AUTOSIZE_USEHEADER)
        self.list_ctrl.SetColumnWidth(0, 1200)

        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        panel.SetSizer(sizer)

        # Barra de status acessível
        self.status_bar = self.CreateStatusBar(1)
        self.status_bar.SetStatusText("Iniciando Accessible Timeline...")

        # Foco inicial na lista
        wx.CallAfter(self.list_ctrl.SetFocus)

    def _init_events(self):
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_FOCUSED, self._on_item_focused)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_item_activated)
        self.list_ctrl.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _on_char_hook(self, event: wx.KeyEvent):
        key = event.GetKeyCode()
        if key == wx.WXK_RETURN:
            self._on_open_details(None)
        elif key == wx.WXK_F5:
            self._on_refresh(None)
        elif key == wx.WXK_F11:
            self._on_toggle_browser(None)
        else:
            event.Skip()

    def _on_item_focused(self, event: wx.ListEvent):
        """Atualiza a posição atual no TimelineStore quando o usuário navega com as setas."""
        if self._updating_ui:
            return
        idx = event.GetIndex()
        if idx >= 0:
            self.store.set_current_index(idx)
            post = self.store.get_post(idx)
            if post:
                self.status_bar.SetStatusText(f"Post {idx + 1} de {self.store.count()} - {post.author_name}")

    def _on_item_activated(self, event: wx.ListEvent):
        """Disparado no Enter ou duplo-clique na lista."""
        self._on_open_details(None)

    def _on_open_details(self, event):
        post = self.store.get_current_post()
        if not post:
            selected = self.list_ctrl.GetFirstSelected()
            if selected != -1:
                post = self.store.get_post(selected)

        if post:
            dlg = PostDetailsDialog(self, post)
            dlg.ShowModal()
            dlg.Destroy()
            self.list_ctrl.SetFocus()
        else:
            wx.Bell()

    def _on_refresh(self, event):
        self.status_bar.SetStatusText("Solicitando atualização da timeline no navegador...")
        self.reader.refresh()

    def _on_load_more(self, event):
        self.status_bar.SetStatusText("Carregando mais postagens...")
        self.reader.load_more()

    def _on_toggle_browser(self, event):
        self.reader.toggle_browser_visibility()
        is_vis = self.reader.is_browser_visible()
        state = "visível" if is_vis else "oculta"
        self.status_bar.SetStatusText(f"Janela do navegador agora está {state}.")

    def _on_about(self, event):
        info = (
            "Accessible Timeline\n\n"
            "Cliente acessível para redes sociais projetado para pessoas com deficiência visual.\n"
            "Fase 1: Suporte a leitura e navegação no X (Twitter) com sessão autenticada.\n\n"
            "Atalhos úteis:\n"
            "- Setas Cima / Baixo: Navegar entre postagens\n"
            "- Enter: Abrir detalhes da postagem\n"
            "- F5: Atualizar timeline\n"
            "- F11: Exibir ou ocultar navegador\n"
            "- Ctrl+M: Carregar mais postagens"
        )
        wx.MessageBox(info, "Sobre o Accessible Timeline", wx.OK | wx.ICON_INFORMATION, self)

    def set_status_message(self, message: str):
        """Atualiza a mensagem na barra de status da janela de forma thread-safe."""
        wx.CallAfter(self.status_bar.SetStatusText, message)

    def _on_store_updated(self, posts: List[Post], current_idx: int):
        """Notificado pelo TimelineStore quando há novas postagens ou alterações."""
        wx.CallAfter(self._sync_ui_list, posts, current_idx)

    def _sync_ui_list(self, posts: List[Post], current_idx: int):
        """Sincroniza a ListCtrl com a lista de posts do store."""
        self._updating_ui = True
        try:
            prev_count = self.list_ctrl.GetItemCount()
            new_count = len(posts)

            # Se a quantidade mudou ou é inicial
            if prev_count != new_count:
                self.list_ctrl.DeleteAllItems()
                for idx, post in enumerate(posts):
                    summary = post.to_accessible_summary()
                    self.list_ctrl.InsertItem(idx, summary)
            else:
                # Atualização de métricas sem mudar contagem
                for idx, post in enumerate(posts):
                    summary = post.to_accessible_summary()
                    self.list_ctrl.SetItemText(idx, summary)

            # Preservar a seleção ativa
            if 0 <= current_idx < new_count:
                self.list_ctrl.Select(current_idx, True)
                self.list_ctrl.Focus(current_idx)
                self.list_ctrl.EnsureVisible(current_idx)

            self.status_bar.SetStatusText(f"Pronto. {new_count} publicações na timeline.")
        finally:
            self._updating_ui = False

    def _on_close(self, event: wx.CloseEvent):
        """Finalização limpa da aplicação e do navegador."""
        self.store.unsubscribe(self._on_store_updated)
        self.status_bar.SetStatusText("Encerrando navegador...")
        # Desliga o leitor e o navegador
        try:
            self.reader.stop()
        except Exception as e:
            logger.error(f"Erro ao parar o leitor: {e}")

        event.Skip()
