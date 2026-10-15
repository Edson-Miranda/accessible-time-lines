"""
Janela principal do Accessible Timeline.
Utiliza controles nativos Win32 (wx.Notebook e wx.ListCtrl) garantindo
compatibilidade total com NVDA, JAWS e demais leitores de tela sem causar anúncios duplicados.
Oferece as guias 'Para você' e 'Seguindo' com alternância por teclado.
"""

import ctypes
import logging
from typing import List, Tuple
import wx
from src.core.models import Post
from src.core.timeline_store import TimelineStore
from src.platforms.x_twitter.reader import XTimelineReader
from src.ui.dialogs import PostDetailsDialog

logger = logging.getLogger("AccessibleTimeline.MainWindow")

# Códigos de teclas virtuais Win32 para Windows Key
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
    def __init__(self, for_you_store: TimelineStore, following_store: TimelineStore, reader: XTimelineReader):
        super().__init__(
            parent=None,
            id=wx.ID_ANY,
            title="Accessible Timeline - X (Twitter)",
            size=(900, 650),
            style=wx.DEFAULT_FRAME_STYLE
        )

        self.for_you_store = for_you_store
        self.following_store = following_store
        self.reader = reader

        self._updating_for_you = False
        self._updating_following = False

        self._init_menu()
        self._init_ui()
        self._init_events()

        # Inscrição para receber atualizações de cada feed
        self.for_you_store.subscribe(self._on_for_you_updated)
        self.following_store.subscribe(self._on_following_updated)

        self.Center()

    def _init_menu(self):
        menu_bar = wx.MenuBar()

        # Menu Timeline
        timeline_menu = wx.Menu()
        item_refresh = timeline_menu.Append(wx.ID_REFRESH, "&Atualizar Guia Ativa\tF5", "Recarrega as postagens da guia selecionada")
        item_load_more = timeline_menu.Append(wx.ID_ANY, "Carregar &Mais Postagens\tCtrl+M", "Solicita rolagem no navegador para mais postagens")
        timeline_menu.AppendSeparator()
        item_switch_tab = timeline_menu.Append(wx.ID_ANY, "Alternar Guia (Para você / Seguindo)\tCtrl+Tab", "Alterna entre as guias de postagens")
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
        self.Bind(wx.EVT_MENU, lambda e: self._toggle_tab(), item_switch_tab)
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
            label="Navegue entre guias com Shift+Tab (ou Ctrl+Win+Setas). Setas Cima e Baixo para posts, Enter para detalhes, F5 para atualizar e F11 para o navegador:"
        )
        sizer.Add(self.info_label, 0, wx.ALL, 8)

        # Controle de Abas nativo do Windows (SysTabControl32)
        self.notebook = wx.Notebook(panel, style=wx.NB_TOP)

        # Aba 0: Para você (Home)
        self.for_you_panel = wx.Panel(self.notebook)
        for_you_sizer = wx.BoxSizer(wx.VERTICAL)
        self.for_you_list = wx.ListCtrl(
            self.for_you_panel,
            style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL
        )
        self.for_you_list.InsertColumn(0, "Publicações - Para você", width=1200)
        for_you_sizer.Add(self.for_you_list, 1, wx.EXPAND)
        self.for_you_panel.SetSizer(for_you_sizer)
        self.notebook.AddPage(self.for_you_panel, "Para você", select=True)

        # Aba 1: Seguindo (Following)
        self.following_panel = wx.Panel(self.notebook)
        following_sizer = wx.BoxSizer(wx.VERTICAL)
        self.following_list = wx.ListCtrl(
            self.following_panel,
            style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL
        )
        self.following_list.InsertColumn(0, "Publicações - Seguindo", width=1200)
        following_sizer.Add(self.following_list, 1, wx.EXPAND)
        self.following_panel.SetSizer(following_sizer)
        self.notebook.AddPage(self.following_panel, "Seguindo", select=False)

        sizer.Add(self.notebook, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        panel.SetSizer(sizer)

        # Barra de status acessível
        self.status_bar = self.CreateStatusBar(1)
        self.status_bar.SetStatusText("Iniciando Accessible Timeline...")

        # Foco inicial na lista 'Para você'
        wx.CallAfter(self.for_you_list.SetFocus)

    def _init_events(self):
        # Evento de mudança de aba no Notebook
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_notebook_page_changed)

        # Eventos das listas
        self.for_you_list.Bind(wx.EVT_LIST_ITEM_FOCUSED, lambda e: self._on_item_focused(e, self.for_you_store, "Para você"))
        self.for_you_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._on_open_details(None))

        self.following_list.Bind(wx.EVT_LIST_ITEM_FOCUSED, lambda e: self._on_item_focused(e, self.following_store, "Seguindo"))
        self.following_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda e: self._on_open_details(None))

        # Captura global de teclas na janela
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_CLOSE, self._on_close)

    def _get_active_feed_info(self) -> Tuple[int, TimelineStore, wx.ListCtrl, str]:
        """Retorna (índice, store, list_ctrl, nome) da guia atualmente selecionada."""
        sel = self.notebook.GetSelection()
        if sel == 1:
            return 1, self.following_store, self.following_list, "following"
        return 0, self.for_you_store, self.for_you_list, "home"

    def _toggle_tab(self, target_index: int = -1):
        """Alterna a guia do notebook e sincroniza o foco."""
        current = self.notebook.GetSelection()
        if target_index < 0:
            target = 1 if current == 0 else 0
        else:
            target = target_index

        if target != current:
            self.notebook.SetSelection(target)
            target_list = self.following_list if target == 1 else self.for_you_list
            wx.CallAfter(target_list.SetFocus)

    def _on_notebook_page_changed(self, event: wx.BookCtrlEvent):
        """Disparado quando o usuário alterna abas pelo controle nativo ou setas."""
        idx = event.GetSelection()
        feed_name = "following" if idx == 1 else "home"
        tab_label = "Seguindo" if idx == 1 else "Para você"
        store = self.following_store if idx == 1 else self.for_you_store
        active_list = self.following_list if idx == 1 else self.for_you_list

        self.reader.switch_feed_tab(feed_name)
        self.status_bar.SetStatusText(f"Guia {tab_label}: {store.count()} publicações.")
        wx.CallAfter(active_list.SetFocus)
        event.Skip()

    def _on_char_hook(self, event: wx.KeyEvent):
        key = event.GetKeyCode()
        ctrl = event.ControlDown()
        win = _is_win_key_down()

        # Atalho Control + Windows + Seta Direita / Esquerda
        if ctrl and win and key in (wx.WXK_RIGHT, wx.WXK_LEFT):
            self._toggle_tab()
            return

        # Atalho padrão Ctrl + Tab
        if ctrl and key == wx.WXK_TAB:
            self._toggle_tab()
            return

        if key == wx.WXK_RETURN:
            self._on_open_details(None)
        elif key == wx.WXK_F5:
            self._on_refresh(None)
        elif key == wx.WXK_F11:
            self._on_toggle_browser(None)
        else:
            event.Skip()

    def _on_item_focused(self, event: wx.ListEvent, store: TimelineStore, feed_label: str):
        idx = event.GetIndex()
        if idx >= 0:
            store.set_current_index(idx)
            post = store.get_post(idx)
            if post:
                self.status_bar.SetStatusText(f"[{feed_label}] Post {idx + 1} de {store.count()} - {post.author_name}")

    def _on_open_details(self, event):
        _, store, active_list, _ = self._get_active_feed_info()
        post = store.get_current_post()
        if not post:
            sel = active_list.GetFirstSelected()
            if sel != -1:
                post = store.get_post(sel)

        if post:
            dlg = PostDetailsDialog(self, post)
            dlg.ShowModal()
            dlg.Destroy()
            active_list.SetFocus()
        else:
            wx.Bell()

    def _on_refresh(self, event):
        _, _, _, feed_name = self._get_active_feed_info()
        label = "Seguindo" if feed_name == "following" else "Para você"
        self.status_bar.SetStatusText(f"Solicitando atualização da guia {label} no navegador...")
        self.reader.refresh(feed_name)

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
            "Guias disponíveis:\n"
            "- Para você (Recomendações algorítmicas)\n"
            "- Seguindo (Timeline cronológica de contas seguidas)\n\n"
            "Atalhos úteis:\n"
            "- Control + Windows + Seta Direita/Esquerda: Alternar entre as guias\n"
            "- Shift + Tab / Tab: Mover o foco entre a lista e o cabeçalho de guias\n"
            "- Setas Cima / Baixo: Navegar entre postagens da guia ativa\n"
            "- Enter: Abrir detalhes da postagem\n"
            "- F5: Atualizar a guia ativa\n"
            "- F11: Exibir ou ocultar navegador\n"
            "- Ctrl+M: Carregar mais postagens"
        )
        wx.MessageBox(info, "Sobre o Accessible Timeline", wx.OK | wx.ICON_INFORMATION, self)

    def set_status_message(self, message: str):
        wx.CallAfter(self.status_bar.SetStatusText, message)

    def _on_for_you_updated(self, posts: List[Post], current_idx: int):
        wx.CallAfter(self._sync_list, self.for_you_list, posts, current_idx, "Para você")

    def _on_following_updated(self, posts: List[Post], current_idx: int):
        wx.CallAfter(self._sync_list, self.following_list, posts, current_idx, "Seguindo")

    def _sync_list(self, list_ctrl: wx.ListCtrl, posts: List[Post], current_idx: int, feed_label: str):
        try:
            prev_count = list_ctrl.GetItemCount()
            new_count = len(posts)

            if prev_count != new_count:
                list_ctrl.DeleteAllItems()
                for idx, post in enumerate(posts):
                    summary = post.to_accessible_summary()
                    list_ctrl.InsertItem(idx, summary)
            else:
                for idx, post in enumerate(posts):
                    summary = post.to_accessible_summary()
                    list_ctrl.SetItemText(idx, summary)

            if 0 <= current_idx < new_count:
                list_ctrl.Select(current_idx, True)
                list_ctrl.Focus(current_idx)
                list_ctrl.EnsureVisible(current_idx)

            sel_tab = self.notebook.GetSelection()
            active_is_this = (sel_tab == 0 and feed_label == "Para você") or (sel_tab == 1 and feed_label == "Seguindo")
            if active_is_this:
                self.status_bar.SetStatusText(f"Pronto. {new_count} publicações na guia {feed_label}.")
        except Exception as e:
            logger.error(f"Erro ao sincronizar lista {feed_label}: {e}")

    def _on_close(self, event: wx.CloseEvent):
        self.for_you_store.unsubscribe(self._on_for_you_updated)
        self.following_store.unsubscribe(self._on_following_updated)
        self.status_bar.SetStatusText("Encerrando navegador...")
        try:
            self.reader.stop()
        except Exception as e:
            logger.error(f"Erro ao parar o leitor: {e}")
        event.Skip()
