"""
Janela principal do Accessible Timeline com visualização em Árvore (SysTreeView32).
Inspirado na arquitetura clássica do TWBlue e The Qube:
Árvore acessível à esquerda com nó da conta expandir/recolher e fluxos
(Para você, Seguindo, Menções/Notificações, Mensagens diretas),
e lista de publicações à direita totalmente operável por teclado.
"""

import ctypes
import logging
from typing import Dict, List, Optional, Tuple
import wx
from src.core.models import Post
from src.core.timeline_store import TimelineStore
from src.platforms.x_twitter.reader import XTimelineReader
from src.ui.dialogs import PostDetailsDialog

logger = logging.getLogger("AccessibleTimeline.MainWindow")

VK_LWIN = 0x5B
VK_RWIN = 0x5C


def _is_win_key_down() -> bool:
    """Verifica se a tecla Windows está pressionada via Win32 GetAsyncKeyState."""
    try:
        left = ctypes.windll.user32.GetAsyncKeyState(VK_LWIN) & 0x8000
        right = ctypes.windll.user32.GetAsyncKeyState(VK_RWIN) & 0x8000
        return bool(left or right)
    except Exception:
        return False


class MainWindow(wx.Frame):
    def __init__(self, stores: Dict[str, TimelineStore], reader: XTimelineReader):
        super().__init__(
            parent=None,
            id=wx.ID_ANY,
            title="Accessible Timeline - X (Twitter)",
            size=(950, 650),
            style=wx.DEFAULT_FRAME_STYLE
        )

        self.stores = stores
        self.reader = reader
        self._active_stream = "for_you"
        self._updating_list = False

        self._init_menu()
        self._init_ui()
        self._init_events()

        # Inscreve cada store para receber atualizações automáticas
        for stream_id, store in self.stores.items():
            store.subscribe(self._create_store_callback(stream_id))

        self.Center()

    def _create_store_callback(self, stream_id: str):
        return lambda posts, idx: self._on_store_updated(stream_id, posts, idx)

    def _init_menu(self):
        menu_bar = wx.MenuBar()

        # Menu Timeline
        timeline_menu = wx.Menu()
        item_refresh = timeline_menu.Append(wx.ID_REFRESH, "&Atualizar Fluxo Ativo\tF5", "Recarrega o fluxo selecionado na árvore")
        item_load_more = timeline_menu.Append(wx.ID_ANY, "Carregar &Mais Postagens\tCtrl+M", "Solicita rolagem no navegador para mais postagens")
        timeline_menu.AppendSeparator()
        item_details = timeline_menu.Append(wx.ID_ANY, "Ver &Detalhes da Publicação\tEnter", "Abre os detalhes da postagem selecionada")
        timeline_menu.AppendSeparator()
        item_exit = timeline_menu.Append(wx.ID_EXIT, "Sai&r\tAlt+F4", "Fecha o Accessible Timeline")
        menu_bar.Append(timeline_menu, "&Timeline")

        # Menu Ajuda
        help_menu = wx.Menu()
        item_about = help_menu.Append(wx.ID_ABOUT, "&Sobre\tF1", "Informações sobre o aplicativo")
        menu_bar.Append(help_menu, "A&juda")

        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self._on_refresh, item_refresh)
        self.Bind(wx.EVT_MENU, self._on_load_more, item_load_more)
        self.Bind(wx.EVT_MENU, self._on_open_details, item_details)
        self.Bind(wx.EVT_MENU, self._on_about, item_about)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), item_exit)

    def _init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Instrução acessível
        self.info_label = wx.StaticText(
            panel,
            label="Árvore de contas e fluxos à esquerda (Tab para posts). Na lista de posts, Shift+Tab volta para a árvore. Atalho Ctrl+Win+Setas para alternar fluxos:"
        )
        main_sizer.Add(self.info_label, 0, wx.ALL, 6)

        # Painel horizontal dividindo Árvore (esquerda) e Lista (direita)
        content_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Árvore nativa Win32 (SysTreeView32)
        self.tree = wx.TreeCtrl(
            panel,
            style=wx.TR_DEFAULT_STYLE | wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_SINGLE
        )

        # Criação dos nós da árvore
        self.account_root = self.tree.AddRoot("Conta X")
        self.item_foryou = self.tree.AppendItem(self.account_root, "Para você")
        self.item_following = self.tree.AppendItem(self.account_root, "Seguindo")
        self.item_mentions = self.tree.AppendItem(self.account_root, "Menções (Notificações)")
        self.item_dms = self.tree.AppendItem(self.account_root, "Mensagens diretas")

        # Mapeamento entre TreeItemId e identificador do fluxo
        self._item_to_stream = {
            self.item_foryou: "for_you",
            self.item_following: "following",
            self.item_mentions: "mentions",
            self.item_dms: "dms",
        }
        self._stream_to_item = {v: k for k, v in self._item_to_stream.items()}
        self._stream_order = ["for_you", "following", "mentions", "dms"]

        self.tree.Expand(self.account_root)
        self.tree.SelectItem(self.item_foryou)
        content_sizer.Add(self.tree, 1, wx.EXPAND | wx.RIGHT, 6)

        # Lista de postagens nativa Win32 (SysListView32)
        self.list_ctrl = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL
        )
        self.list_ctrl.InsertColumn(0, "Publicações", width=1200)
        content_sizer.Add(self.list_ctrl, 3, wx.EXPAND)

        main_sizer.Add(content_sizer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        panel.SetSizer(main_sizer)

        # Barra de status acessível
        self.status_bar = self.CreateStatusBar(1)
        self.status_bar.SetStatusText("Iniciando Accessible Timeline...")

        # Foco inicial na lista de postagens
        wx.CallAfter(self.list_ctrl.SetFocus)

    def _init_events(self):
        # Eventos da Árvore
        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self._on_tree_selection_changed)
        self.tree.Bind(wx.EVT_TREE_ITEM_ACTIVATED, self._on_tree_item_activated)

        # Eventos da Lista
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_FOCUSED, self._on_item_focused)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._on_open_details(None))

        # Captura global de teclas
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def set_account_name(self, name: str):
        """Atualiza o rótulo do nó da conta na árvore com o nome detectado."""
        def _update():
            try:
                self.tree.SetItemText(self.account_root, name)
            except Exception as e:
                logger.debug(f"Erro ao atualizar rótulo da conta: {e}")
        wx.CallAfter(_update)

    def _on_tree_selection_changed(self, event: wx.TreeEvent):
        item = event.GetItem()
        if not item.IsOk() or item == self.account_root:
            return

        stream_id = self._item_to_stream.get(item)
        if stream_id and stream_id != self._active_stream:
            self._switch_to_stream(stream_id, notify_browser=True)

    def _on_tree_item_activated(self, event: wx.TreeEvent):
        """No Enter sobre a árvore, entra diretamente na lista de publicações."""
        item = event.GetItem()
        if item and item != self.account_root:
            wx.CallAfter(self.list_ctrl.SetFocus)
        else:
            event.Skip()

    def _switch_to_stream(self, stream_id: str, notify_browser: bool = True):
        """Alterna o fluxo ativo e renderiza as postagens correspondentes."""
        self._active_stream = stream_id
        tree_item = self._stream_to_item.get(stream_id)
        if tree_item and self.tree.GetSelection() != tree_item:
            self.tree.SelectItem(tree_item)

        store = self.stores.get(stream_id)
        if store:
            self._sync_list(store.get_all_posts(), store.get_current_index())
            label = self._get_stream_display_name(stream_id)
            self.status_bar.SetStatusText(f"{label}: {store.count()} publicações.")

        if notify_browser:
            self.reader.switch_feed_tab(stream_id)

    def _get_stream_display_name(self, stream_id: str) -> str:
        names = {
            "for_you": "Para você",
            "following": "Seguindo",
            "mentions": "Menções (Notificações)",
            "dms": "Mensagens diretas"
        }
        return names.get(stream_id, stream_id)

    def _cycle_stream(self, forward: bool = True):
        """Avança ou recua para o próximo fluxo na árvore."""
        try:
            curr_idx = self._stream_order.index(self._active_stream)
        except ValueError:
            curr_idx = 0

        next_idx = (curr_idx + 1) if forward else (curr_idx - 1)
        if next_idx >= len(self._stream_order):
            next_idx = 0
        elif next_idx < 0:
            next_idx = len(self._stream_order) - 1

        next_stream = self._stream_order[next_idx]
        self._switch_to_stream(next_stream, notify_browser=True)
        wx.CallAfter(self.list_ctrl.SetFocus)

    def _on_char_hook(self, event: wx.KeyEvent):
        key = event.GetKeyCode()
        ctrl = event.ControlDown()
        win = _is_win_key_down()

        # Atalho Ctrl + Win + Setas (Cima/Baixo/Direita/Esquerda) para alternar fluxos da árvore
        if ctrl and win and key in (wx.WXK_DOWN, wx.WXK_RIGHT):
            self._cycle_stream(forward=True)
            return
        elif ctrl and win and key in (wx.WXK_UP, wx.WXK_LEFT):
            self._cycle_stream(forward=False)
            return

        # Atalho clássico Ctrl + Tab para próximo fluxo
        if ctrl and key == wx.WXK_TAB:
            shift = event.ShiftDown()
            self._cycle_stream(forward=not shift)
            return

        if key == wx.WXK_RETURN:
            # Se o foco estiver na lista, abre os detalhes
            focused = wx.Window.FindFocus()
            if focused == self.list_ctrl:
                self._on_open_details(None)
                return
            event.Skip()
        elif key == wx.WXK_F5:
            self._on_refresh(None)
        else:
            event.Skip()

    def _on_item_focused(self, event: wx.ListEvent):
        if self._updating_list:
            return
        idx = event.GetIndex()
        store = self.stores.get(self._active_stream)
        if store and idx >= 0:
            store.set_current_index(idx)
            post = store.get_post(idx)
            if post:
                label = self._get_stream_display_name(self._active_stream)
                self.status_bar.SetStatusText(f"[{label}] Post {idx + 1} de {store.count()} - {post.author_name}")

    def _on_open_details(self, event):
        store = self.stores.get(self._active_stream)
        if not store:
            return
        post = store.get_current_post()
        if not post:
            sel = self.list_ctrl.GetFirstSelected()
            if sel != -1:
                post = store.get_post(sel)

        if post:
            dlg = PostDetailsDialog(self, post)
            dlg.ShowModal()
            dlg.Destroy()
            self.list_ctrl.SetFocus()
        else:
            wx.Bell()

    def _on_refresh(self, event):
        label = self._get_stream_display_name(self._active_stream)
        self.status_bar.SetStatusText(f"Solicitando atualização de {label} no navegador...")
        self.reader.refresh(self._active_stream)

    def _on_load_more(self, event):
        self.status_bar.SetStatusText("Carregando mais postagens...")
        self.reader.load_more()

    def _on_about(self, event):
        info = (
            "Accessible Timeline\n\n"
            "Cliente acessível para redes sociais projetado para pessoas com deficiência visual.\n"
            "Fase 1: Suporte a leitura e navegação no X (Twitter) com sessão autenticada.\n\n"
            "Navegação na Árvore e Lista:\n"
            "- Árvore (esquerda): Nó da conta com os fluxos Para você, Seguindo, Menções e Mensagens diretas.\n"
            "- Tab / Shift+Tab: Alternar o foco entre a Árvore de fluxos e a Lista de postagens.\n"
            "- Setas Cima / Baixo na lista: Ler publicações do fluxo ativo.\n"
            "- Control + Windows + Setas: Alternar rapidamente entre os fluxos.\n"
            "- Enter: Abrir detalhes completos da postagem.\n"
            "- F5: Atualizar o fluxo ativo.\n"
            "- Ctrl+M: Carregar mais postagens."
        )
        wx.MessageBox(info, "Sobre o Accessible Timeline", wx.OK | wx.ICON_INFORMATION, self)

    def set_status_message(self, message: str):
        wx.CallAfter(self.status_bar.SetStatusText, message)

    def _on_store_updated(self, stream_id: str, posts: List[Post], current_idx: int):
        """Notificado quando um store recebe postagens."""
        if stream_id == self._active_stream:
            wx.CallAfter(self._sync_list, posts, current_idx)

    def _sync_list(self, posts: List[Post], current_idx: int):
        """Sincroniza a ListCtrl com a lista de posts do store ativo."""
        self._updating_list = True
        try:
            prev_count = self.list_ctrl.GetItemCount()
            new_count = len(posts)

            if prev_count != new_count:
                self.list_ctrl.DeleteAllItems()
                for idx, post in enumerate(posts):
                    summary = post.to_accessible_summary()
                    self.list_ctrl.InsertItem(idx, summary)
            else:
                for idx, post in enumerate(posts):
                    summary = post.to_accessible_summary()
                    self.list_ctrl.SetItemText(idx, summary)

            if 0 <= current_idx < new_count:
                self.list_ctrl.Select(current_idx, True)
                self.list_ctrl.Focus(current_idx)
                self.list_ctrl.EnsureVisible(current_idx)

            label = self._get_stream_display_name(self._active_stream)
            self.status_bar.SetStatusText(f"Pronto. {new_count} publicações em {label}.")
        finally:
            self._updating_list = False

    def _on_close(self, event: wx.CloseEvent):
        self.status_bar.SetStatusText("Encerrando navegador...")
        try:
            self.reader.stop()
        except Exception as e:
            logger.error(f"Erro ao parar o leitor: {e}")
        event.Skip()
