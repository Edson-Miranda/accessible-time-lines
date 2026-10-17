"""
Janela principal do Accessible Timeline com visualização em Árvore (SysTreeView32).
Inspirado na arquitetura clássica do TWBlue e The Qube:
Árvore acessível à esquerda com nó da conta expandir/recolher e fluxos
(Para você, Seguindo, Menções/Notificações, Mensagens diretas),
e lista de publicações à direita totalmente operável por teclado.
"""

import ctypes
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple
import threading
import webbrowser
import wx
import wx.adv
from src.core.models import Post
from src.core.timeline_store import TimelineStore
from src.core.version import __version__
from src.core.updater import (
    check_for_updates,
    get_application_directory,
    apply_update_and_restart,
)
from src.core.config import config_manager, DEFAULT_SHORTCUTS, DEFAULT_GLOBAL_SHORTCUTS
from src.platforms.x_twitter.reader import XTimelineReader
from src.platforms.x_twitter.executor import XActionExecutor
from src.audio.manager import sound_manager
from src.audio.speech import speech_manager
from src.ui.dialogs import (
    PostDetailsDialog,
    SelectLinkDialog,
    NewPostDialog,
    ReplyDialog,
    QuoteDialog,
    RetweetChoiceDialog,
    SendDMDialog,
    SettingsDialog,
    UpdateDownloadDialog,
    SearchUsersDialog,
    UserTimelineDialog,
)

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


def parse_shortcut_to_wx(shortcut_str: str) -> Optional[Tuple[int, int]]:
    """Converte string de atalho (ex: 'Ctrl+Win+H', 'Ctrl+Win+Down') em modificadores e tecla wx."""
    parts = [p.strip().lower() for p in shortcut_str.split("+")]
    mods = 0
    key = None
    for p in parts:
        if p in ("ctrl", "control"):
            mods |= wx.MOD_CONTROL
        elif p in ("win", "windows", "super", "meta"):
            mods |= wx.MOD_WIN
        elif p == "shift":
            mods |= wx.MOD_SHIFT
        elif p == "alt":
            mods |= wx.MOD_ALT
        elif len(p) == 1:
            key = ord(p.upper())
        elif p == "down":
            key = wx.WXK_DOWN
        elif p == "up":
            key = wx.WXK_UP
        elif p == "right":
            key = wx.WXK_RIGHT
        elif p == "left":
            key = wx.WXK_LEFT
        elif p.startswith("f") and p[1:].isdigit():
            fn = int(p[1:])
            key = getattr(wx, f"WXK_F{fn}", None)
        elif p in ("enter", "return"):
            key = wx.WXK_RETURN
        elif p == "space":
            key = wx.WXK_SPACE
        elif p == "tab":
            key = wx.WXK_TAB
        elif p in ("esc", "escape"):
            key = wx.WXK_ESCAPE
    if key is not None:
        return (mods, key)
    return None


HOTKEY_ACTION_MAP = {
    "toggle_visibility": 1001,
    "next_post": 1002,
    "prev_post": 1003,
    "next_stream": 1004,
    "prev_stream": 1005,
    "new_post": 1006,
    "reply": 1007,
    "like": 1008,
    "copy_text": 1009,
}
HOTKEY_ID_TO_ACTION = {v: k for k, v in HOTKEY_ACTION_MAP.items()}


class TimelineTaskBarIcon(wx.adv.TaskBarIcon):
    """Ícone na área de notificação do Windows com menu de contexto acessível."""
    def __init__(self, frame: wx.Frame):
        super().__init__()
        self.frame = frame
        self._set_icon()
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self._on_toggle)

    def _set_icon(self):
        try:
            # Tenta carregar ícone local
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            icon_path = os.path.join(base_dir, "tw blue", "icon.ico")
            if os.path.exists(icon_path):
                icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO)
                if icon.IsOk():
                    self.SetIcon(icon, "Accessible Timeline")
        except Exception as e:
            logger.debug(f"Não foi possível carregar ícone da bandeja: {e}")

    def CreatePopupMenu(self):
        menu = wx.Menu()
        show_label = "Ocultar Accessible Timeline" if self.frame.IsShown() else "Exibir Accessible Timeline"
        item_toggle = menu.Append(wx.ID_ANY, show_label)
        menu.AppendSeparator()
        item_new = menu.Append(wx.ID_ANY, "Nova Publicação...")
        menu.AppendSeparator()
        item_exit = menu.Append(wx.ID_EXIT, "Sair do Accessible Timeline")

        menu.Bind(wx.EVT_MENU, self._on_toggle, item_toggle)
        menu.Bind(wx.EVT_MENU, self._on_new_post, item_new)
        menu.Bind(wx.EVT_MENU, self._on_exit, item_exit)
        return menu

    def _on_toggle(self, event):
        self.frame._toggle_window_visibility()

    def _on_new_post(self, event):
        self.frame.Show()
        self.frame.Raise()
        self.frame._on_new_post(None)

    def _on_exit(self, event):
        self.frame._real_exit()


class MainWindow(wx.Frame):
    def __init__(
        self,
        stores: Dict[str, TimelineStore],
        reader: XTimelineReader,
        executor: Optional[XActionExecutor] = None
    ):
        super().__init__(
            parent=None,
            id=wx.ID_ANY,
            title=f"Accessible Timeline v{__version__} - X (Twitter)",
            size=(950, 650),
            style=wx.DEFAULT_FRAME_STYLE
        )

        self.stores = stores
        self.reader = reader
        self.executor = executor or XActionExecutor(reader.browser_manager)
        self._active_stream = "for_you"
        self._updating_list = False
        self._is_exiting = False
        self._registered_hotkeys: Set[int] = set()

        # Inicializa preferências salvas de áudio
        sound_manager.enabled = config_manager.get("sound_enabled", True)
        sound_theme = config_manager.get("sound_theme", "default")
        sound_manager.set_theme(sound_theme)

        # Inicializa ícone de bandeja se suportado
        self.taskbar_icon: Optional[TimelineTaskBarIcon] = None
        try:
            self.taskbar_icon = TimelineTaskBarIcon(self)
        except Exception as e:
            logger.debug(f"TaskBarIcon indisponível: {e}")

        self._init_menu()
        self._init_ui()
        self._init_events()

        # Registra teclas de atalho globais de segundo plano (Win+Ctrl / Win+Alt)
        self._register_global_hotkeys()

        # Inscreve cada store para receber atualizações automáticas
        for stream_id, store in self.stores.items():
            store.subscribe(self._create_store_callback(stream_id))

        self.Center()

        # Verificação automática e silenciosa de atualizações após inicialização se habilitada
        if config_manager.get("check_updates_automatically", True):
            wx.CallLater(3500, lambda: self._check_updates_worker(silent=True))

    def _create_store_callback(self, stream_id: str):
        return lambda posts, idx: self._on_store_updated(stream_id, posts, idx)

    def _init_menu(self):
        menu_bar = wx.MenuBar()

        # Menu Timeline
        timeline_menu = wx.Menu()
        item_refresh = timeline_menu.Append(wx.ID_REFRESH, "&Atualizar Fluxo Ativo\tF5", "Recarrega o fluxo selecionado na árvore")
        item_load_more = timeline_menu.Append(wx.ID_ANY, "Carregar &Mais Postagens\tCtrl+M", "Solicita rolagem no navegador para mais postagens")
        timeline_menu.AppendSeparator()
        item_user_timeline = timeline_menu.Append(wx.ID_ANY, "Abrir &Linha do Tempo de Usuário...\tCtrl+U", "Abre as postagens de um usuário específico do X")
        timeline_menu.AppendSeparator()
        item_details = timeline_menu.Append(wx.ID_ANY, "Ver &Detalhes da Publicação\tEnter", "Abre os detalhes da postagem selecionada")
        item_open_link = timeline_menu.Append(wx.ID_ANY, "Abrir &Link no Navegador\tCtrl+Enter", "Abre o link da postagem selecionada no navegador padrão")
        timeline_menu.AppendSeparator()
        item_toggle_browser = timeline_menu.Append(wx.ID_ANY, "Alternar Janela do &Navegador (Login / Verificação)\tCtrl+Shift+M", "Exibe ou oculta a janela do navegador Chromium")
        timeline_menu.AppendSeparator()
        item_exit = timeline_menu.Append(wx.ID_EXIT, "Sai&r\tAlt+F4", "Fecha o Accessible Timeline")
        menu_bar.Append(timeline_menu, "&Timeline")

        # Menu Ações
        actions_menu = wx.Menu()
        item_new_post = actions_menu.Append(wx.ID_ANY, "&Nova Publicação...\tCtrl+N", "Compor e publicar um novo tweet")
        item_reply = actions_menu.Append(wx.ID_ANY, "&Responder...\tCtrl+R", "Responder à publicação selecionada")
        item_retweet = actions_menu.Append(wx.ID_ANY, "Re&postar...\tCtrl+Shift+R", "Repostar ou citar a publicação selecionada")
        item_quote = actions_menu.Append(wx.ID_ANY, "Repostar com &Comentário (Citar)...\tCtrl+Shift+C", "Citar a publicação selecionada com comentário")
        actions_menu.AppendSeparator()
        item_like = actions_menu.Append(wx.ID_ANY, "&Curtir / Descurtir\tCtrl+L", "Curte ou remove a curtida da publicação selecionada")
        actions_menu.AppendSeparator()
        item_dm = actions_menu.Append(wx.ID_ANY, "Enviar &Mensagem Direta (DM)...\tCtrl+D", "Envia uma mensagem direta para o autor da publicação")
        actions_menu.AppendSeparator()
        item_search_users = actions_menu.Append(wx.ID_ANY, "Buscar &Usuários...\tCtrl+Shift+U", "Pesquisa usuários no X e permite ver perfil e timeline")
        item_follow = actions_menu.Append(wx.ID_ANY, "Se&guir Autor\tCtrl+Shift+F", "Começa a seguir o autor da publicação selecionada")
        item_unfollow = actions_menu.Append(wx.ID_ANY, "&Deixar de Seguir Autor\tCtrl+Alt+F", "Deixa de seguir o autor da publicação selecionada")
        item_block = actions_menu.Append(wx.ID_ANY, "&Bloquear Autor\tCtrl+Shift+B", "Bloqueia o autor da publicação selecionada")
        menu_bar.Append(actions_menu, "&Ações")

        # Menu Áudio (Sons do TWBlue)
        audio_menu = wx.Menu()
        self.item_sound_enabled = audio_menu.AppendCheckItem(wx.ID_ANY, "Ativar Efeitos &Sonoros\tCtrl+Shift+S", "Liga ou desliga a reprodução dos sons do TWBlue")
        self.item_sound_enabled.Check(sound_manager.enabled)

        themes_menu = wx.Menu()
        self._sound_themes = ["default", "classic", "Qwitter", "Magical Fountain", "FreakyBlue", "FightingGames"]
        self._theme_menu_items = {}
        for th in self._sound_themes:
            m_item = themes_menu.AppendRadioItem(wx.ID_ANY, th)
            if th == sound_manager.theme_name:
                m_item.Check(True)
            self._theme_menu_items[m_item.GetId()] = th
            self.Bind(wx.EVT_MENU, self._on_select_sound_theme, m_item)

        audio_menu.AppendSubMenu(themes_menu, "&Pacote de Sons do TWBlue")
        menu_bar.Append(audio_menu, "Á&udio")

        # Menu Opções
        options_menu = wx.Menu()
        item_settings = options_menu.Append(wx.ID_PREFERENCES, "&Configurações...\tCtrl+P", "Preferências e configurações do aplicativo")
        menu_bar.Append(options_menu, "&Opções")

        # Menu Ajuda
        help_menu = wx.Menu()
        item_check_updates = help_menu.Append(wx.ID_ANY, "&Verificar Atualizações...", "Verifica se há uma versão mais recente do Accessible Timeline")
        help_menu.AppendSeparator()
        item_about = help_menu.Append(wx.ID_ABOUT, "&Sobre\tF1", "Informações sobre o aplicativo")
        menu_bar.Append(help_menu, "A&juda")

        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self._on_refresh, item_refresh)
        self.Bind(wx.EVT_MENU, self._on_load_more, item_load_more)
        self.Bind(wx.EVT_MENU, self._on_open_user_timeline, item_user_timeline)
        self.Bind(wx.EVT_MENU, self._on_open_details, item_details)
        self.Bind(wx.EVT_MENU, self._on_open_link, item_open_link)
        self.Bind(wx.EVT_MENU, self._on_toggle_browser, item_toggle_browser)
        self.Bind(wx.EVT_MENU, self._on_new_post, item_new_post)
        self.Bind(wx.EVT_MENU, self._on_reply, item_reply)
        self.Bind(wx.EVT_MENU, self._on_retweet, item_retweet)
        self.Bind(wx.EVT_MENU, self._on_quote, item_quote)
        self.Bind(wx.EVT_MENU, self._on_toggle_like, item_like)
        self.Bind(wx.EVT_MENU, self._on_send_dm, item_dm)
        self.Bind(wx.EVT_MENU, self._on_search_users, item_search_users)
        self.Bind(wx.EVT_MENU, self._on_follow_author, item_follow)
        self.Bind(wx.EVT_MENU, self._on_unfollow_author, item_unfollow)
        self.Bind(wx.EVT_MENU, self._on_block_author, item_block)
        self.Bind(wx.EVT_MENU, self._on_toggle_sound, self.item_sound_enabled)
        self.Bind(wx.EVT_MENU, self._on_settings, item_settings)
        self.Bind(wx.EVT_MENU, self._on_check_updates, item_check_updates)
        self.Bind(wx.EVT_MENU, self._on_about, item_about)
        self.Bind(wx.EVT_MENU, lambda e: self._real_exit(), item_exit)

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
        self.item_sent = self.tree.AppendItem(self.account_root, "Enviados")

        # Mapeamento entre TreeItemId e identificador do fluxo
        self._item_to_stream = {
            self.item_foryou: "for_you",
            self.item_following: "following",
            self.item_mentions: "mentions",
            self.item_dms: "dms",
            self.item_sent: "sent",
        }
        self._stream_to_item = {v: k for k, v in self._item_to_stream.items()}
        self._stream_order = ["for_you", "following", "mentions", "dms", "sent"]

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

        # Captura global de teclas na janela e atalhos globais do SO
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_HOTKEY, self._on_global_hotkey)
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
            "dms": "Mensagens diretas",
            "sent": "Enviados",
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
        alt = event.AltDown()
        shift = event.ShiftDown()
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
            self._cycle_stream(forward=not shift)
            return

        # Atalhos de Usuários (TWBlue):
        # Ctrl + Shift + U: Buscar Usuários
        if ctrl and shift and not win and not alt and key in (ord('U'), ord('u')):
            self._on_search_users(None)
            return

        # Ctrl + U: Abrir Linha do Tempo de Usuário
        if ctrl and not shift and not win and not alt and key in (ord('U'), ord('u')):
            self._on_open_user_timeline(None)
            return

        # Ctrl + Shift + F: Seguir Autor
        if ctrl and shift and not win and not alt and key in (ord('F'), ord('f')):
            self._on_follow_author(None)
            return

        # Ctrl + Alt + F: Deixar de Seguir Autor
        if ctrl and alt and not win and not shift and key in (ord('F'), ord('f')):
            self._on_unfollow_author(None)
            return

        # Ctrl + Shift + B: Bloquear Autor
        if ctrl and shift and not win and not alt and key in (ord('B'), ord('b')):
            self._on_block_author(None)
            return

        # Ctrl + Shift + M: Alternar Janela do Navegador
        if ctrl and shift and not win and not alt and key in (ord('M'), ord('m')):
            self._on_toggle_browser(None)
            return

        # Atalhos de Ações (TWBlue / The Qube):
        # Ctrl + N: Nova publicação
        if ctrl and not shift and not win and not alt and key in (ord('N'), ord('n')):
            self._on_new_post(None)
            return

        # Ctrl + R: Responder
        if ctrl and not shift and not win and not alt and key in (ord('R'), ord('r')):
            self._on_reply(None)
            return

        # Ctrl + Shift + R: Repostar / Retweet
        if ctrl and shift and not win and not alt and key in (ord('R'), ord('r')):
            self._on_retweet(None)
            return

        # Ctrl + Shift + C: Citar com comentário
        if ctrl and shift and not win and not alt and key in (ord('C'), ord('c')):
            self._on_quote(None)
            return

        # Ctrl + D: Enviar Mensagem Direta (DM)
        if ctrl and not shift and not win and not alt and key in (ord('D'), ord('d')):
            self._on_send_dm(None)
            return

        # Ctrl + L ou tecla L (na lista): Curtir / Descurtir
        if ctrl and not shift and not win and not alt and key in (ord('L'), ord('l')):
            self._on_toggle_like(None)
            return
        elif not ctrl and not shift and not win and not alt and key in (ord('L'), ord('l')):
            focused = wx.Window.FindFocus()
            if focused == self.list_ctrl:
                self._on_toggle_like(None)
                return

        # Atalho Ctrl + Enter (ou Ctrl + Numpad Enter) para abrir links no navegador
        if ctrl and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_open_link(None)
            return

        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
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

    def _on_open_link(self, event=None):
        """Abre o link no navegador padrão ou exibe caixa de combinação para múltiplos links."""
        store = self.stores.get(self._active_stream)
        if not store:
            return
        post = store.get_current_post()
        if not post:
            sel = self.list_ctrl.GetFirstSelected()
            if sel != -1:
                post = store.get_post(sel)

        if not post:
            wx.Bell()
            return

        links = post.get_all_links()
        if not links:
            self.status_bar.SetStatusText("Nenhum link disponível nesta publicação.")
            wx.Bell()
            return

        if len(links) == 1:
            target_url = links[0]
            self.status_bar.SetStatusText(f"Abrindo link no navegador padrão: {target_url}")
            webbrowser.open(target_url)
        else:
            dlg = SelectLinkDialog(self, links, post_author=post.author_name)
            if dlg.ShowModal() == wx.ID_OK:
                selected_url = dlg.get_selected_link()
                if selected_url:
                    self.status_bar.SetStatusText(f"Abrindo link no navegador padrão: {selected_url}")
                    webbrowser.open(selected_url)
            dlg.Destroy()
            self.list_ctrl.SetFocus()

    def _on_toggle_sound(self, event):
        """Alterna a ativação dos efeitos sonoros do TWBlue."""
        sound_manager.enabled = self.item_sound_enabled.IsChecked()
        config_manager.set("sound_enabled", sound_manager.enabled)
        state = "ativados" if sound_manager.enabled else "desativados"
        self.set_status_message(f"Efeitos sonoros {state}.")

    def _on_select_sound_theme(self, event):
        """Altera o pacote de som do TWBlue."""
        theme = self._theme_menu_items.get(event.GetId())
        if theme:
            sound_manager.set_theme(theme)
            config_manager.set("sound_theme", theme)
            self.set_status_message(f"Pacote de som alterado para: {theme}")
            sound_manager.play_ready()

    def _on_settings(self, event=None):
        """Abre a janela de configurações do aplicativo."""
        dlg = SettingsDialog(self)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                # Recarrega preferências atualizadas
                sound_manager.enabled = config_manager.get("sound_enabled", True)
                sound_manager.set_theme(config_manager.get("sound_theme", "default"))
                self._unregister_global_hotkeys()
                self._register_global_hotkeys()
                store = self.stores.get(self._active_stream)
                if store:
                    self._sync_list(store.get_all_posts(), store.get_current_index())
        finally:
            dlg.Destroy()
        self.list_ctrl.SetFocus()

    def _on_new_post(self, event=None):
        """Abre o diálogo acessível para compor e publicar um novo tweet."""
        dlg = NewPostDialog(self)
        if dlg.ShowModal() == wx.ID_OK:
            text = dlg.get_text()
            if text:
                self.status_bar.SetStatusText("Enviando publicação para o X...")
                def _success():
                    self.set_status_message("Publicação enviada com sucesso!")
                    sound_manager.play_tweet_sent()
                    self._add_to_sent_store(text)
                def _error():
                    self.set_status_message("Falha ao enviar publicação. Tente novamente.")
                    sound_manager.play_error()
                self.executor.run_async(lambda: self.executor.create_post(text), on_success=_success, on_error=_error)
        dlg.Destroy()
        self.list_ctrl.SetFocus()

    def _on_reply(self, event=None):
        """Abre o diálogo para responder à publicação selecionada."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if not post:
            sel = self.list_ctrl.GetFirstSelected()
            if sel != -1 and store:
                post = store.get_post(sel)

        if not post:
            wx.Bell()
            self.status_bar.SetStatusText("Nenhuma publicação selecionada para responder.")
            return

        dlg = ReplyDialog(self, post)
        if dlg.ShowModal() == wx.ID_OK:
            text = dlg.get_text()
            if text:
                self.status_bar.SetStatusText(f"Enviando resposta para @{post.author_username}...")
                def _success():
                    self.set_status_message(f"Resposta enviada para @{post.author_username} com sucesso!")
                    sound_manager.play_reply_sent()
                    self._add_to_sent_store(text, reply_to=post.author_username)
                def _error():
                    self.set_status_message(f"Falha ao enviar resposta para @{post.author_username}.")
                    sound_manager.play_error()
                self.executor.run_async(
                    lambda: self.executor.reply_to_post(post.id, text, post.author_username),
                    on_success=_success,
                    on_error=_error
                )
        dlg.Destroy()
        self.list_ctrl.SetFocus()

    def _on_retweet(self, event=None):
        """Abre o diálogo de escolha entre repostar direto ou citar com comentário."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if not post:
            sel = self.list_ctrl.GetFirstSelected()
            if sel != -1 and store:
                post = store.get_post(sel)

        if not post:
            wx.Bell()
            self.status_bar.SetStatusText("Nenhuma publicação selecionada para repostar.")
            return

        choice_dlg = RetweetChoiceDialog(self, post)
        result = choice_dlg.ShowModal()
        choice_dlg.Destroy()

        if result == wx.ID_YES:
            # Repostar diretamente
            self.status_bar.SetStatusText(f"Repostando publicação de @{post.author_username}...")
            def _success():
                self.set_status_message(f"Publicação de @{post.author_username} repostada com sucesso!")
                sound_manager.play_retweet_sent()
            def _error():
                self.set_status_message("Falha ao repostar publicação.")
                sound_manager.play_error()
            self.executor.run_async(
                lambda: self.executor.retweet_post(post.id),
                on_success=_success,
                on_error=_error
            )
            self.list_ctrl.SetFocus()
        elif result == wx.ID_NO:
            # Citar com comentário
            self._on_quote(None)

    def _on_quote(self, event=None):
        """Abre o diálogo para citar a publicação selecionada com comentário."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if not post:
            sel = self.list_ctrl.GetFirstSelected()
            if sel != -1 and store:
                post = store.get_post(sel)

        if not post:
            wx.Bell()
            self.status_bar.SetStatusText("Nenhuma publicação selecionada para citar.")
            return

        dlg = QuoteDialog(self, post)
        if dlg.ShowModal() == wx.ID_OK:
            comment = dlg.get_text()
            if comment:
                self.status_bar.SetStatusText(f"Publicando citação de @{post.author_username}...")
                def _success():
                    self.set_status_message("Citação publicada com sucesso!")
                    sound_manager.play_tweet_sent()
                    self._add_to_sent_store(comment)
                def _error():
                    self.set_status_message("Falha ao publicar citação.")
                    sound_manager.play_error()
                self.executor.run_async(
                    lambda: self.executor.quote_post(post.id, comment, post.url),
                    on_success=_success,
                    on_error=_error
                )
        dlg.Destroy()
        self.list_ctrl.SetFocus()

    def _on_toggle_like(self, event=None):
        """Curte a publicação selecionada no X."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if not post:
            sel = self.list_ctrl.GetFirstSelected()
            if sel != -1 and store:
                post = store.get_post(sel)

        if not post:
            wx.Bell()
            self.status_bar.SetStatusText("Nenhuma publicação selecionada para curtir.")
            return

        self.status_bar.SetStatusText(f"Processando curtida para publicação de @{post.author_username}...")
        def _success():
            self.set_status_message(f"Publicação de @{post.author_username} curtida com sucesso!")
            sound_manager.play_favourite()
        def _error():
            self.set_status_message("Falha ao processar curtida.")
            sound_manager.play_error()
        self.executor.run_async(
            lambda: self.executor.like_post(post.id),
            on_success=_success,
            on_error=_error
        )

    def _on_send_dm(self, event=None):
        """Abre o diálogo para enviar mensagem direta (DM)."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if not post:
            sel = self.list_ctrl.GetFirstSelected()
            if sel != -1 and store:
                post = store.get_post(sel)

        initial_user = post.author_username if post else ""
        dlg = SendDMDialog(self, initial_recipient=initial_user)
        if dlg.ShowModal() == wx.ID_OK:
            recipient, message = dlg.get_data()
            if recipient and message:
                self.status_bar.SetStatusText(f"Enviando mensagem direta para @{recipient}...")
                def _success():
                    self.set_status_message(f"Mensagem direta enviada para @{recipient} com sucesso!")
                    sound_manager.play_dm_sent()
                def _error():
                    self.set_status_message(f"Falha ao enviar mensagem direta para @{recipient}.")
                    sound_manager.play_error()
                self.executor.run_async(
                    lambda: self.executor.send_dm(recipient, message),
                    on_success=_success,
                    on_error=_error
                )
        dlg.Destroy()
        self.list_ctrl.SetFocus()

    def _on_refresh(self, event):
        label = self._get_stream_display_name(self._active_stream)
        self.status_bar.SetStatusText(f"Solicitando atualização de {label} no navegador...")
        self.reader.refresh(self._active_stream)

    def _on_load_more(self, event):
        self.status_bar.SetStatusText("Carregando mais postagens...")
        self.reader.load_more()

    def _on_toggle_browser(self, event=None):
        """Alterna a visibilidade da janela do navegador Chromium."""
        self.reader.toggle_browser_window()

    def _on_about(self, event):
        info = (
            f"Accessible Timeline v{__version__}\n"
            "Desenvolvido por TechTales Entertainment\n"
            "Site oficial: https://techtales.com.br\n\n"
            "Cliente acessível para redes sociais projetado para pessoas com deficiência visual.\n"
            "Inspirado no TWBlue e The Qube com foco prioritário em leitores de tela (NVDA e JAWS).\n\n"
            "Navegação por Teclado:\n"
            "- Árvore (esquerda): Nó da conta com os fluxos Para você, Seguindo, Menções e Mensagens diretas.\n"
            "- Tab / Shift+Tab: Alternar o foco entre a Árvore de fluxos e a Lista de postagens.\n"
            "- Setas Cima / Baixo na lista: Ler publicações do fluxo ativo (leitura do texto completo).\n"
            "- Control + Windows + Setas: Alternar rapidamente entre os fluxos.\n"
            "- Enter: Abrir detalhes completos da postagem.\n"
            "- Control + Enter: Abrir link no navegador padrão (com diálogo de seleção para múltiplos links).\n"
            "- Ctrl + Shift + B: Alternar exibição da janela do navegador (para fazer login ou resolver verificações).\n"
            "- F5: Atualizar o fluxo ativo.\n"
            "- Ctrl+M: Carregar mais postagens.\n\n"
            "Comandos e Ações (Menu Ações ou Atalhos Rápidos):\n"
            "- Ctrl + N: Nova publicação (Tweet) com contador de caracteres.\n"
            "- Ctrl + R: Responder à publicação selecionada.\n"
            "- Ctrl + Shift + R: Repostar diretamente ou citar.\n"
            "- Ctrl + Shift + C: Repostar com comentário (Citar).\n"
            "- Ctrl + L ou tecla L: Curtir / Descurtir a publicação selecionada.\n"
            "- Ctrl + D: Enviar Mensagem Direta (DM) para o autor selecionado.\n\n"
            "Opções e Preferências (Menu Opções):\n"
            "- Ctrl + P: Configurações do aplicativo (ativar / desativar verificação automática de atualizações).\n\n"
            "Efeitos Sonoros (Menu Áudio):\n"
            "- Sons clássicos do TWBlue para ações, notificações e avisos de limite de texto.\n"
            "- Ctrl + Shift + S: Ativar / Desativar efeitos sonoros.\n"
            "- Seleção de temas sonoros: Padrão (TWBlue), Clássico, Qwitter, Magical Fountain, FreakyBlue e FightingGames.\n\n"
            "TechTales Entertainment - https://techtales.com.br"
        )
        wx.MessageBox(info, f"Sobre o Accessible Timeline v{__version__}", wx.OK | wx.ICON_INFORMATION, self)

    def _check_updates_worker(self, silent: bool = False):
        """Verifica se há uma nova versão disponível no GitHub Releases."""
        if not silent:
            self.status_bar.SetStatusText("Verificando se há atualizações disponíveis no GitHub...")

        def _worker():
            info = check_for_updates()

            def _ui_result():
                if info:
                    latest = info['latest_version']
                    msg = (
                        f"Uma nova versão do Accessible Timeline está disponível!\n\n"
                        f"Versão atual: {__version__}\n"
                        f"Nova versão: {latest}\n\n"
                        f"Deseja baixar e instalar a atualização agora?"
                    )
                    res = wx.MessageBox(msg, "Atualização Disponível", wx.YES_NO | wx.ICON_INFORMATION, self)
                    if res == wx.YES:
                        self._perform_update_download(info)
                elif not silent:
                    msg = f"Você já está utilizando a versão mais recente do Accessible Timeline (v{__version__})."
                    wx.MessageBox(msg, "Nenhuma Atualização Disponível", wx.OK | wx.ICON_INFORMATION, self)
                if not silent:
                    self.status_bar.SetStatusText("Pronto.")

            wx.CallAfter(_ui_result)

        threading.Thread(target=_worker, daemon=True, name="CheckUpdatesThread").start()

    def _perform_update_download(self, info: dict):
        """Baixa o pacote compactado da atualização e aplica diretamente na pasta da aplicação."""
        download_url = info.get("download_url") or info.get("html_url", "")
        # Se for link direto para arquivo zip, utiliza o baixador embutido
        if download_url and (download_url.endswith(".zip") or "/releases/download/" in download_url):
            dlg = UpdateDownloadDialog(
                self,
                download_url=download_url,
                new_version=info.get("latest_version", "")
            )
            try:
                res = dlg.ShowModal()
                if res == wx.ID_OK:
                    zip_path = dlg.get_zip_path()
                    if zip_path and os.path.exists(zip_path):
                        target_dir = get_application_directory()
                        confirm_msg = (
                            f"O download da versão {info.get('latest_version')} foi concluído com sucesso!\n\n"
                            f"O aplicativo será reiniciado para extrair e aplicar os arquivos na pasta de instalação:\n"
                            f"{target_dir}\n\n"
                            f"Deseja fechar o Accessible Timeline e atualizar agora?"
                        )
                        restart_res = wx.MessageBox(
                            confirm_msg,
                            "Aplicar Atualização",
                            wx.YES_NO | wx.ICON_INFORMATION,
                            self
                        )
                        if restart_res == wx.YES:
                            self.status_bar.SetStatusText("Aplicando atualização e reiniciando...")
                            current_pid = os.getpid()
                            success = apply_update_and_restart(zip_path, target_dir, current_pid)
                            if success:
                                self.Close(True)
                                return
                            else:
                                wx.MessageBox(
                                    "Não foi possível iniciar o assistente de atualização automática.\n"
                                    "Você pode extrair o arquivo compactado manualmente se desejar.",
                                    "Erro ao Aplicar",
                                    wx.OK | wx.ICON_ERROR,
                                    self
                                )
            finally:
                dlg.Destroy()
        else:
            # Fallback caso não seja um link direto de arquivo compactado
            webbrowser.open(download_url or info.get("html_url", ""))

    def _on_check_updates(self, event=None):
        """Ação acionada pelo menu Ajuda > Verificar Atualizações..."""
        self._check_updates_worker(silent=False)

    def set_status_message(self, message: str, speak: bool = True):
        wx.CallAfter(self.status_bar.SetStatusText, message)
        if speak and config_manager.get("speak_status_alerts", True):
            speech_manager.speak(message, interrupt=False)

    def _add_to_sent_store(self, text: str, reply_to: str = ""):
        """Adiciona localmente a publicação recém-enviada ao fluxo de 'Enviados'."""
        my_user = getattr(self.reader.browser_manager, "_my_username", "") or "Você"
        sent_post = Post(
            id=f"sent_{int(time.time() * 1000)}",
            platform="x_twitter",
            author_name=my_user,
            author_username=my_user,
            text=text,
            created_at=datetime.now(),
            created_at_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            is_reply=bool(reply_to),
            replying_to=reply_to or None
        )
        sent_store = self.stores.get("sent")
        if sent_store:
            sent_store.prepend_post(sent_post)

    def _register_global_hotkeys(self):
        """Registra teclas de atalho globais no Windows para controle em segundo plano."""
        if not config_manager.get("global_hotkeys_enabled", True):
            return
        global_shortcuts = config_manager.get("global_shortcuts", DEFAULT_GLOBAL_SHORTCUTS)
        self._registered_hotkeys = set()
        for action, shortcut_str in global_shortcuts.items():
            hid = HOTKEY_ACTION_MAP.get(action)
            if not hid:
                continue
            parsed = parse_shortcut_to_wx(shortcut_str)
            if parsed:
                mod, key = parsed
                try:
                    res = self.RegisterHotKey(hid, mod, key)
                    if res:
                        self._registered_hotkeys.add(hid)
                    else:
                        logger.debug(f"Falha ao registrar tecla global '{shortcut_str}' para '{action}'.")
                except Exception as e:
                    logger.debug(f"Exceção ao registrar tecla global '{shortcut_str}': {e}")

    def _unregister_global_hotkeys(self):
        """Desregistra todas as teclas globais ativas."""
        for hid in getattr(self, "_registered_hotkeys", set()):
            try:
                self.UnregisterHotKey(hid)
            except Exception:
                pass
        self._registered_hotkeys = set()

    def _on_global_hotkey(self, event):
        """Processa eventos de teclas de atalho globais do sistema operacional."""
        hid = event.GetId()
        action = HOTKEY_ID_TO_ACTION.get(hid)
        if not action:
            return

        if action == "toggle_visibility":
            self._toggle_window_visibility()
        elif action == "next_post":
            self._navigate_post_in_background(forward=True)
        elif action == "prev_post":
            self._navigate_post_in_background(forward=False)
        elif action == "next_stream":
            self._cycle_stream_in_background(forward=True)
        elif action == "prev_stream":
            self._cycle_stream_in_background(forward=False)
        elif action == "copy_text":
            self._copy_current_post_text()
        elif action == "like":
            self._on_toggle_like(None)
        elif action == "new_post":
            self.Show()
            self.Raise()
            self.SetFocus()
            self._on_new_post(None)
        elif action == "reply":
            self.Show()
            self.Raise()
            self.SetFocus()
            self._on_reply(None)

    def _toggle_window_visibility(self):
        """Alterna a exibição e o ocultamento da janela principal com anúncio via fala."""
        if self.IsShown():
            self.Hide()
            speech_manager.speak("Accessible Timeline oculto.", interrupt=True)
        else:
            self.Show()
            self.Raise()
            self.SetFocus()
            speech_manager.speak("Accessible Timeline exibido.", interrupt=True)

    def _navigate_post_in_background(self, forward: bool = True):
        """Navega entre publicações em segundo plano com fala direta sem roubar o foco do SO."""
        store = self.stores.get(self._active_stream)
        if not store or store.count() == 0:
            speech_manager.speak("Nenhuma publicação disponível neste fluxo.", interrupt=True)
            return
        idx = store.get_current_index()
        new_idx = (idx + 1) if forward else (idx - 1)
        if 0 <= new_idx < store.count():
            store.set_current_index(new_idx)
            post = store.get_post(new_idx)
            if post:
                speech_manager.speak(post.to_accessible_summary(), interrupt=True)
            if self.IsShown():
                self.list_ctrl.Select(new_idx, True)
                self.list_ctrl.Focus(new_idx)
                self.list_ctrl.EnsureVisible(new_idx)
        else:
            sound_manager.play_border()

    def _cycle_stream_in_background(self, forward: bool = True):
        """Alterna o fluxo ativo em segundo plano com fala direta."""
        self._cycle_stream(forward=forward)
        label = self._get_stream_display_name(self._active_stream)
        store = self.stores.get(self._active_stream)
        count = store.count() if store else 0
        speech_manager.speak(f"{label}. {count} publicações.", interrupt=True)

    def _copy_current_post_text(self):
        """Copia o texto da postagem selecionada para a área de transferência."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if post and post.text:
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(post.text))
                wx.TheClipboard.Close()
                speech_manager.speak("Texto da publicação copiado para a área de transferência.", interrupt=True)
        else:
            speech_manager.speak("Nenhuma publicação selecionada.", interrupt=True)

    def _on_search_users(self, event=None):
        """Abre o diálogo acessível de busca de usuários no X."""
        dlg = SearchUsersDialog(self, self.executor)
        try:
            dlg.ShowModal()
        finally:
            dlg.Destroy()
        self.list_ctrl.SetFocus()

    def _on_open_user_timeline(self, event=None):
        """Abre diálogo para informar @usuário e exibir sua linha do tempo."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        initial_user = post.author_username if post else ""
        dlg = wx.TextEntryDialog(
            self,
            "Digite o @nome_de_usuario (sem o @) para abrir a linha do tempo:",
            "Abrir Linha do Tempo de Usuário",
            value=initial_user
        )
        if dlg.ShowModal() == wx.ID_OK:
            username = dlg.GetValue().strip().lstrip("@")
            dlg.Destroy()
            if username:
                timeline_dlg = UserTimelineDialog(self, self.executor, username)
                try:
                    timeline_dlg.ShowModal()
                finally:
                    timeline_dlg.Destroy()
                self.list_ctrl.SetFocus()
        else:
            dlg.Destroy()

    def _on_follow_author(self, event=None):
        """Começa a seguir o autor da publicação selecionada."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if not post:
            self.set_status_message("Nenhuma publicação selecionada para seguir o autor.")
            wx.Bell()
            return
        username = post.author_username
        self.set_status_message(f"Seguindo @{username} no X...")
        def _success():
            self.set_status_message(f"Agora você está seguindo @{username}!")
            sound_manager.play_favourite()
        def _error():
            self.set_status_message(f"Falha ao seguir @{username}.")
            sound_manager.play_error()
        self.executor.run_async(lambda: self.executor.follow_user(username), on_success=_success, on_error=_error)

    def _on_unfollow_author(self, event=None):
        """Deixa de seguir o autor da publicação selecionada."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if not post:
            self.set_status_message("Nenhuma publicação selecionada para deixar de seguir o autor.")
            wx.Bell()
            return
        username = post.author_username
        confirm = wx.MessageBox(
            f"Deseja realmente deixar de seguir @{username}?",
            "Confirmar Deixar de Seguir",
            wx.YES_NO | wx.ICON_QUESTION,
            self
        )
        if confirm != wx.YES:
            return
        self.set_status_message(f"Deixando de seguir @{username} no X...")
        def _success():
            self.set_status_message(f"Você deixou de seguir @{username}.")
        def _error():
            self.set_status_message(f"Falha ao deixar de seguir @{username}.")
            sound_manager.play_error()
        self.executor.run_async(lambda: self.executor.unfollow_user(username), on_success=_success, on_error=_error)

    def _on_block_author(self, event=None):
        """Bloqueia o autor da publicação selecionada no X."""
        store = self.stores.get(self._active_stream)
        post = store.get_current_post() if store else None
        if not post:
            self.set_status_message("Nenhuma publicação selecionada para bloquear o autor.")
            wx.Bell()
            return
        username = post.author_username
        confirm = wx.MessageBox(
            f"Deseja realmente bloquear @{username} no X?\nEle não poderá mais ver seu perfil ou interagir com você.",
            "Confirmar Bloqueio de Usuário",
            wx.YES_NO | wx.ICON_WARNING,
            self
        )
        if confirm != wx.YES:
            return
        self.set_status_message(f"Bloqueando @{username} no X...")
        def _success():
            self.set_status_message(f"Usuário @{username} foi bloqueado com sucesso.")
        def _error():
            self.set_status_message(f"Falha ao bloquear @{username}.")
            sound_manager.play_error()
        self.executor.run_async(lambda: self.executor.block_user(username), on_success=_success, on_error=_error)

    def _real_exit(self):
        """Encerra a aplicação forçando a saída mesmo com minimizar para bandeja ativado."""
        self._is_exiting = True
        self.Close(force=True)

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
            elif new_count > 0:
                self.list_ctrl.Select(0, True)
                self.list_ctrl.Focus(0)
                self.list_ctrl.EnsureVisible(0)

            label = self._get_stream_display_name(self._active_stream)
            self.status_bar.SetStatusText(f"Pronto. {new_count} publicações em {label}.")
        finally:
            self._updating_list = False

    def _on_close(self, event: wx.CloseEvent):
        # Minimiza para bandeja se ativado e não estiver forçando encerramento
        if not self._is_exiting and config_manager.get("hide_to_tray_on_close", False):
            event.Veto()
            self.Hide()
            speech_manager.speak("Accessible Timeline minimizado para a bandeja do sistema.", interrupt=True)
            return

        self._is_exiting = True
        self._unregister_global_hotkeys()
        if self.taskbar_icon:
            try:
                self.taskbar_icon.RemoveIcon()
                self.taskbar_icon.Destroy()
            except Exception:
                pass
            self.taskbar_icon = None

        self.status_bar.SetStatusText("Encerrando navegador...")
        try:
            self.reader.stop()
        except Exception as e:
            logger.error(f"Erro ao parar o leitor: {e}")
        event.Skip()
