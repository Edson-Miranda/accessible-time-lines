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
import threading
import webbrowser
import wx
from src.core.models import Post
from src.core.timeline_store import TimelineStore
from src.core.version import __version__
from src.core.updater import check_for_updates
from src.platforms.x_twitter.reader import XTimelineReader
from src.platforms.x_twitter.executor import XActionExecutor
from src.audio.manager import sound_manager
from src.ui.dialogs import (
    PostDetailsDialog,
    SelectLinkDialog,
    NewPostDialog,
    ReplyDialog,
    QuoteDialog,
    RetweetChoiceDialog,
    SendDMDialog,
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
        item_open_link = timeline_menu.Append(wx.ID_ANY, "Abrir &Link no Navegador\tCtrl+Enter", "Abre o link da postagem selecionada no navegador padrão")
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

        # Menu Ajuda
        help_menu = wx.Menu()
        item_check_updates = help_menu.Append(wx.ID_ANY, "&Verificar Atualizações...", "Verifica se há uma versão mais recente do Accessible Timeline")
        help_menu.AppendSeparator()
        item_about = help_menu.Append(wx.ID_ABOUT, "&Sobre\tF1", "Informações sobre o aplicativo")
        menu_bar.Append(help_menu, "A&juda")

        self.SetMenuBar(menu_bar)

        self.Bind(wx.EVT_MENU, self._on_refresh, item_refresh)
        self.Bind(wx.EVT_MENU, self._on_load_more, item_load_more)
        self.Bind(wx.EVT_MENU, self._on_open_details, item_details)
        self.Bind(wx.EVT_MENU, self._on_open_link, item_open_link)
        self.Bind(wx.EVT_MENU, self._on_new_post, item_new_post)
        self.Bind(wx.EVT_MENU, self._on_reply, item_reply)
        self.Bind(wx.EVT_MENU, self._on_retweet, item_retweet)
        self.Bind(wx.EVT_MENU, self._on_quote, item_quote)
        self.Bind(wx.EVT_MENU, self._on_toggle_like, item_like)
        self.Bind(wx.EVT_MENU, self._on_send_dm, item_dm)
        self.Bind(wx.EVT_MENU, self._on_toggle_sound, self.item_sound_enabled)
        self.Bind(wx.EVT_MENU, self._on_check_updates, item_check_updates)
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

        shift = event.ShiftDown()

        # Atalhos de Ações (TWBlue / The Qube):
        # Ctrl + N: Nova publicação
        if ctrl and not shift and not win and key in (ord('N'), ord('n')):
            self._on_new_post(None)
            return

        # Ctrl + R: Responder
        if ctrl and not shift and not win and key in (ord('R'), ord('r')):
            self._on_reply(None)
            return

        # Ctrl + Shift + R: Repostar / Retweet
        if ctrl and shift and not win and key in (ord('R'), ord('r')):
            self._on_retweet(None)
            return

        # Ctrl + Shift + C: Citar com comentário
        if ctrl and shift and not win and key in (ord('C'), ord('c')):
            self._on_quote(None)
            return

        # Ctrl + D: Enviar Mensagem Direta (DM)
        if ctrl and not shift and not win and key in (ord('D'), ord('d')):
            self._on_send_dm(None)
            return

        # Ctrl + L ou tecla L (na lista): Curtir / Descurtir
        if ctrl and not shift and not win and key in (ord('L'), ord('l')):
            self._on_toggle_like(None)
            return
        elif not ctrl and not shift and not win and key in (ord('L'), ord('l')):
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
        state = "ativados" if sound_manager.enabled else "desativados"
        self.set_status_message(f"Efeitos sonoros {state}.")

    def _on_select_sound_theme(self, event):
        """Altera o pacote de som do TWBlue."""
        theme = self._theme_menu_items.get(event.GetId())
        if theme:
            sound_manager.set_theme(theme)
            self.set_status_message(f"Pacote de som alterado para: {theme}")
            sound_manager.play_ready()

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

    def _on_about(self, event):
        info = (
            f"Accessible Timeline v{__version__}\n\n"
            "Cliente acessível para redes sociais projetado para pessoas com deficiência visual.\n"
            "Inspirado no TWBlue e The Qube com foco prioritário em leitores de tela (NVDA e JAWS).\n\n"
            "Navegação por Teclado:\n"
            "- Árvore (esquerda): Nó da conta com os fluxos Para você, Seguindo, Menções e Mensagens diretas.\n"
            "- Tab / Shift+Tab: Alternar o foco entre a Árvore de fluxos e a Lista de postagens.\n"
            "- Setas Cima / Baixo na lista: Ler publicações do fluxo ativo (leitura do texto completo).\n"
            "- Control + Windows + Setas: Alternar rapidamente entre os fluxos.\n"
            "- Enter: Abrir detalhes completos da postagem.\n"
            "- Control + Enter: Abrir link no navegador padrão (com diálogo de seleção para múltiplos links).\n"
            "- F5: Atualizar o fluxo ativo.\n"
            "- Ctrl+M: Carregar mais postagens.\n\n"
            "Comandos e Ações (Menu Ações ou Atalhos Rápidos):\n"
            "- Ctrl + N: Nova publicação (Tweet) com contador de caracteres.\n"
            "- Ctrl + R: Responder à publicação selecionada.\n"
            "- Ctrl + Shift + R: Repostar diretamente ou citar.\n"
            "- Ctrl + Shift + C: Repostar com comentário (Citar).\n"
            "- Ctrl + L ou tecla L: Curtir / Descurtir a publicação selecionada.\n"
            "- Ctrl + D: Enviar Mensagem Direta (DM) para o autor selecionado.\n\n"
            "Efeitos Sonoros (Menu Áudio):\n"
            "- Sons clássicos do TWBlue para ações, notificações e avisos de limite de texto.\n"
            "- Ctrl + Shift + S: Ativar / Desativar efeitos sonoros.\n"
            "- Seleção de temas sonoros: Padrão (TWBlue), Clássico, Qwitter, Magical Fountain, FreakyBlue e FightingGames."
        )
        wx.MessageBox(info, f"Sobre o Accessible Timeline v{__version__}", wx.OK | wx.ICON_INFORMATION, self)

    def _on_check_updates(self, event=None):
        """Verifica se há uma nova versão disponível no GitHub Releases."""
        self.status_bar.SetStatusText("Verificando se há atualizações disponíveis no GitHub...")

        def _worker():
            info = check_for_updates()

            def _ui_result():
                if info:
                    msg = (
                        f"Uma nova versão do Accessible Timeline está disponível!\n\n"
                        f"Versão atual: {__version__}\n"
                        f"Nova versão: {info['latest_version']}\n\n"
                        f"Deseja abrir a página de download agora?"
                    )
                    res = wx.MessageBox(msg, "Atualização Disponível", wx.YES_NO | wx.ICON_INFORMATION, self)
                    if res == wx.YES:
                        webbrowser.open(info.get("download_url") or info.get("html_url"))
                else:
                    msg = f"Você já está utilizando a versão mais recente do Accessible Timeline (v{__version__})."
                    wx.MessageBox(msg, "Nenhuma Atualização Disponível", wx.OK | wx.ICON_INFORMATION, self)
                self.status_bar.SetStatusText("Pronto.")

            wx.CallAfter(_ui_result)

        threading.Thread(target=_worker, daemon=True, name="CheckUpdatesThread").start()

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
            elif new_count > 0:
                self.list_ctrl.Select(0, True)
                self.list_ctrl.Focus(0)
                self.list_ctrl.EnsureVisible(0)

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
