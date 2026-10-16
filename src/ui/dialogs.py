import os
import tempfile
import threading
import webbrowser
from typing import List, Optional
import wx
from src.core.models import Post
from src.audio.manager import sound_manager
from src.core.config import config_manager


class SelectLinkDialog(wx.Dialog):
    """
    Diálogo acessível com caixa de combinação para o usuário escolher
    qual link deseja abrir no navegador quando uma publicação possui múltiplos links.
    """
    def __init__(self, parent: wx.Window, links: List[str], post_author: str = ""):
        title = f"Escolher link - {post_author}" if post_author else "Escolher link para abrir"
        super().__init__(
            parent,
            title=title,
            size=(560, 220),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.links = links
        self.selected_link: Optional[str] = links[0] if links else None
        self._init_ui()
        self.CenterOnParent()

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Rótulo acessível com acelerador de teclado (&S)
        label = wx.StaticText(panel, label="&Selecione o link que deseja abrir no navegador:")
        sizer.Add(label, 0, wx.ALL, 10)

        # Caixa de combinação nativa Win32 (SysComboBox32)
        # O modo ReadOnly permite navegação direta e fluida por setas no NVDA e JAWS
        self.combo = wx.ComboBox(
            panel,
            choices=self.links,
            style=wx.CB_DROPDOWN | wx.CB_READONLY
        )
        if self.links:
            self.combo.SetSelection(0)
        sizer.Add(self.combo, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Linha de botões acessíveis
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        open_btn = wx.Button(panel, wx.ID_OK, label="&Abrir Link")
        open_btn.SetDefault()
        btn_sizer.Add(open_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancelar")
        btn_sizer.Add(cancel_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(sizer)

        self.Bind(wx.EVT_BUTTON, self._on_confirm, id=wx.ID_OK)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        # Foco inicial na caixa de combinação para o leitor de tela anunciar imediatamente
        wx.CallAfter(self.combo.SetFocus)

    def _on_confirm(self, event):
        idx = self.combo.GetSelection()
        if idx != wx.NOT_FOUND and 0 <= idx < len(self.links):
            self.selected_link = self.links[idx]
        elif self.combo.GetValue():
            self.selected_link = self.combo.GetValue()
        self.EndModal(wx.ID_OK)

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_confirm(event)
        else:
            event.Skip()

    def get_selected_link(self) -> Optional[str]:
        return self.selected_link


class PostDetailsDialog(wx.Dialog):
    """
    Exibe o conteúdo completo da publicação em uma caixa de texto acessível.
    Permite leitura linha a linha, caractere por caractere e cópia de conteúdo.
    """
    def __init__(self, parent: wx.Window, post: Post):
        super().__init__(
            parent,
            title=f"Detalhes da publicação de {post.author_name}",
            size=(600, 450),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.post = post
        self._init_ui()
        self.CenterOnParent()

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Rótulo acessível para o leitor de tela
        label = wx.StaticText(panel, label="Conteúdo completo da publicação:")
        sizer.Add(label, 0, wx.ALL, 10)

        # Caixa de texto acessível somente-leitura com scroll
        self.text_ctrl = wx.TextCtrl(
            panel,
            value=self.post.to_accessible_full(),
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
        )
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        # Linha de botões acessíveis
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        copy_btn = wx.Button(panel, label="&Copiar Texto")
        copy_btn.Bind(wx.EVT_BUTTON, self._on_copy)
        btn_sizer.Add(copy_btn, 0, wx.RIGHT, 10)

        links = self.post.get_all_links()
        if links:
            open_link_btn = wx.Button(panel, label="&Abrir Link no Navegador")
            open_link_btn.Bind(wx.EVT_BUTTON, self._on_open_link)
            btn_sizer.Add(open_link_btn, 0, wx.RIGHT, 10)

        close_btn = wx.Button(panel, wx.ID_CANCEL, label="&Fechar")
        btn_sizer.Add(close_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(sizer)

        # Atalho Escape para fechar
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        
        # Foco inicial no texto para o leitor de tela ler imediatamente
        wx.CallAfter(self.text_ctrl.SetFocus)

    def _on_copy(self, event):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(self.post.to_accessible_full()))
            wx.TheClipboard.Close()
            wx.MessageBox("Texto copiado para a área de transferência.", "Copiado", wx.OK | wx.ICON_INFORMATION, self)

    def _on_open_link(self, event):
        links = self.post.get_all_links()
        if not links:
            wx.MessageBox("Nenhum link encontrado nesta publicação.", "Sem links", wx.OK | wx.ICON_INFORMATION, self)
            return

        if len(links) == 1:
            webbrowser.open(links[0])
        else:
            dlg = SelectLinkDialog(self, links, post_author=self.post.author_name)
            if dlg.ShowModal() == wx.ID_OK:
                selected = dlg.get_selected_link()
                if selected:
                    webbrowser.open(selected)
            dlg.Destroy()

    def _on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()


class NewPostDialog(wx.Dialog):
    """
    Diálogo acessível para composição e publicação de novo post/tweet.
    Inclui contador de caracteres dinâmico (limite 280) e atalho Ctrl+Enter para envio.
    """
    MAX_CHARS = 280

    def __init__(self, parent: wx.Window):
        super().__init__(
            parent,
            title="Nova Publicação (280 caracteres restantes)",
            size=(580, 320),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.text_content = ""
        self._init_ui()
        self.CenterOnParent()

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.label = wx.StaticText(panel, label="&O que está acontecendo?")
        sizer.Add(self.label, 0, wx.ALL, 10)

        self.text_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER
        )
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.post_btn = wx.Button(panel, wx.ID_OK, label="&Publicar")
        self.post_btn.SetDefault()
        btn_sizer.Add(self.post_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancelar")
        btn_sizer.Add(cancel_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(sizer)

        self.text_ctrl.Bind(wx.EVT_TEXT, self._on_text_changed)
        self.Bind(wx.EVT_BUTTON, self._on_submit, id=wx.ID_OK)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        wx.CallAfter(self.text_ctrl.SetFocus)

    def _on_text_changed(self, event):
        length = len(self.text_ctrl.GetValue())
        remaining = self.MAX_CHARS - length
        if remaining >= 0:
            self.SetTitle(f"Nova Publicação ({remaining} caracteres restantes)")
            self.post_btn.Enable(length > 0)
        else:
            self.SetTitle(f"Nova Publicação ({abs(remaining)} caracteres a mais!)")
            self.post_btn.Enable(False)
            sound_manager.play_max_length()

    def _on_submit(self, event):
        text = self.text_ctrl.GetValue().strip()
        if not text:
            wx.MessageBox("Digite o texto da publicação antes de enviar.", "Aviso", wx.OK | wx.ICON_WARNING, self)
            return
        if len(text) > self.MAX_CHARS:
            wx.MessageBox("O texto excede o limite de 280 caracteres.", "Limite excedido", wx.OK | wx.ICON_WARNING, self)
            return
        self.text_content = text
        self.EndModal(wx.ID_OK)

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        ctrl = event.ControlDown()
        if ctrl and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_submit(event)
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def get_text(self) -> str:
        return self.text_content


class ReplyDialog(wx.Dialog):
    """
    Diálogo acessível para responder a uma publicação no X.
    """
    MAX_CHARS = 280

    def __init__(self, parent: wx.Window, post: Post):
        super().__init__(
            parent,
            title=f"Responder a @{post.author_username} (280 restantes)",
            size=(600, 420),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.post = post
        self.text_content = ""
        self._init_ui()
        self.CenterOnParent()

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Informações do post que está sendo respondido
        orig_label = wx.StaticText(panel, label=f"Em resposta a {self.post.author_name} (@{self.post.author_username}):")
        sizer.Add(orig_label, 0, wx.ALL, 10)

        self.orig_text = wx.TextCtrl(
            panel,
            value=self.post.text,
            size=(-1, 70),
            style=wx.TE_MULTILINE | wx.TE_READONLY
        )
        sizer.Add(self.orig_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Campo da resposta
        reply_label = wx.StaticText(panel, label="&Sua Resposta:")
        sizer.Add(reply_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.text_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER
        )
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.reply_btn = wx.Button(panel, wx.ID_OK, label="&Responder")
        self.reply_btn.SetDefault()
        btn_sizer.Add(self.reply_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancelar")
        btn_sizer.Add(cancel_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(sizer)

        self.text_ctrl.Bind(wx.EVT_TEXT, self._on_text_changed)
        self.Bind(wx.EVT_BUTTON, self._on_submit, id=wx.ID_OK)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        wx.CallAfter(self.text_ctrl.SetFocus)

    def _on_text_changed(self, event):
        length = len(self.text_ctrl.GetValue())
        remaining = self.MAX_CHARS - length
        if remaining >= 0:
            self.SetTitle(f"Responder a @{self.post.author_username} ({remaining} restantes)")
            self.reply_btn.Enable(length > 0)
        else:
            self.SetTitle(f"Responder a @{self.post.author_username} ({abs(remaining)} caracteres a mais!)")
            self.reply_btn.Enable(False)
            sound_manager.play_max_length()

    def _on_submit(self, event):
        text = self.text_ctrl.GetValue().strip()
        if not text:
            wx.MessageBox("Digite o texto da sua resposta.", "Aviso", wx.OK | wx.ICON_WARNING, self)
            return
        if len(text) > self.MAX_CHARS:
            wx.MessageBox("A resposta excede o limite de 280 caracteres.", "Limite excedido", wx.OK | wx.ICON_WARNING, self)
            return
        self.text_content = text
        self.EndModal(wx.ID_OK)

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        ctrl = event.ControlDown()
        if ctrl and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_submit(event)
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def get_text(self) -> str:
        return self.text_content


class QuoteDialog(wx.Dialog):
    """
    Diálogo acessível para citar/repostar uma publicação com comentário.
    """
    MAX_CHARS = 250

    def __init__(self, parent: wx.Window, post: Post):
        super().__init__(
            parent,
            title=f"Citar publicação de @{post.author_username} ({self.MAX_CHARS} restantes)",
            size=(600, 420),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.post = post
        self.text_content = ""
        self._init_ui()
        self.CenterOnParent()

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        orig_label = wx.StaticText(panel, label=f"Citando publicação de {self.post.author_name} (@{self.post.author_username}):")
        sizer.Add(orig_label, 0, wx.ALL, 10)

        self.orig_text = wx.TextCtrl(
            panel,
            value=self.post.text,
            size=(-1, 70),
            style=wx.TE_MULTILINE | wx.TE_READONLY
        )
        sizer.Add(self.orig_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        quote_label = wx.StaticText(panel, label="&Seu comentário da citação:")
        sizer.Add(quote_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.text_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER
        )
        sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.quote_btn = wx.Button(panel, wx.ID_OK, label="&Publicar Citação")
        self.quote_btn.SetDefault()
        btn_sizer.Add(self.quote_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancelar")
        btn_sizer.Add(cancel_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(sizer)

        self.text_ctrl.Bind(wx.EVT_TEXT, self._on_text_changed)
        self.Bind(wx.EVT_BUTTON, self._on_submit, id=wx.ID_OK)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        wx.CallAfter(self.text_ctrl.SetFocus)

    def _on_text_changed(self, event):
        length = len(self.text_ctrl.GetValue())
        remaining = self.MAX_CHARS - length
        if remaining >= 0:
            self.SetTitle(f"Citar publicação de @{self.post.author_username} ({remaining} restantes)")
            self.quote_btn.Enable(length > 0)
        else:
            self.SetTitle(f"Citar publicação de @{self.post.author_username} ({abs(remaining)} caracteres a mais!)")
            self.quote_btn.Enable(False)
            sound_manager.play_max_length()

    def _on_submit(self, event):
        text = self.text_ctrl.GetValue().strip()
        if not text:
            wx.MessageBox("Digite seu comentário para a citação.", "Aviso", wx.OK | wx.ICON_WARNING, self)
            return
        if len(text) > self.MAX_CHARS:
            wx.MessageBox("O comentário excede o limite de caracteres.", "Limite excedido", wx.OK | wx.ICON_WARNING, self)
            return
        self.text_content = text
        self.EndModal(wx.ID_OK)

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        ctrl = event.ControlDown()
        if ctrl and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_submit(event)
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def get_text(self) -> str:
        return self.text_content


class RetweetChoiceDialog(wx.Dialog):
    """
    Diálogo acessível para o usuário decidir entre Repostar diretamente ou Citar com comentário.
    """
    def __init__(self, parent: wx.Window, post: Post):
        super().__init__(
            parent,
            title=f"Repostar - {post.author_name}",
            size=(480, 190),
            style=wx.DEFAULT_DIALOG_STYLE
        )
        self.post = post
        self._init_ui()
        self.CenterOnParent()

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        msg = wx.StaticText(
            panel,
            label=f"Deseja repostar diretamente a publicação de {self.post.author_name} (@{self.post.author_username}) ou adicionar um comentário?"
        )
        sizer.Add(msg, 0, wx.ALL, 15)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.retweet_btn = wx.Button(panel, wx.ID_YES, label="&Repostar Diretamente")
        self.retweet_btn.SetDefault()
        btn_sizer.Add(self.retweet_btn, 0, wx.RIGHT, 10)

        quote_btn = wx.Button(panel, wx.ID_NO, label="&Citar com Comentário...")
        btn_sizer.Add(quote_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancelar")
        btn_sizer.Add(cancel_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        panel.SetSizer(sizer)

        self.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_YES), id=wx.ID_YES)
        self.Bind(wx.EVT_BUTTON, lambda e: self.EndModal(wx.ID_NO), id=wx.ID_NO)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        wx.CallAfter(self.retweet_btn.SetFocus)

    def _on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()


class SendDMDialog(wx.Dialog):
    """
    Diálogo acessível para envio de mensagem direta (DM) no X.
    """
    def __init__(self, parent: wx.Window, initial_recipient: str = ""):
        super().__init__(
            parent,
            title="Enviar Mensagem Direta (DM)",
            size=(560, 360),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self.initial_recipient = initial_recipient.lstrip("@")
        self.recipient_value = ""
        self.message_value = ""
        self._init_ui()
        self.CenterOnParent()

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        user_label = wx.StaticText(panel, label="&Destinatário (nome de usuário sem @):")
        sizer.Add(user_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self.recipient_ctrl = wx.TextCtrl(panel, value=self.initial_recipient)
        sizer.Add(self.recipient_ctrl, 0, wx.EXPAND | wx.ALL, 10)

        msg_label = wx.StaticText(panel, label="&Mensagem privada:")
        sizer.Add(msg_label, 0, wx.LEFT | wx.RIGHT, 10)

        self.message_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE | wx.TE_PROCESS_ENTER
        )
        sizer.Add(self.message_ctrl, 1, wx.EXPAND | wx.ALL, 10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.send_btn = wx.Button(panel, wx.ID_OK, label="&Enviar DM")
        self.send_btn.SetDefault()
        btn_sizer.Add(self.send_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancelar")
        btn_sizer.Add(cancel_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        panel.SetSizer(sizer)

        self.Bind(wx.EVT_BUTTON, self._on_submit, id=wx.ID_OK)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

        # Se já tem destinatário, foca na mensagem; senão, no destinatário
        if self.initial_recipient:
            wx.CallAfter(self.message_ctrl.SetFocus)
        else:
            wx.CallAfter(self.recipient_ctrl.SetFocus)

    def _on_submit(self, event):
        recipient = self.recipient_ctrl.GetValue().lstrip("@").strip()
        text = self.message_ctrl.GetValue().strip()

        if not recipient:
            wx.MessageBox("Informe o nome de usuário do destinatário.", "Aviso", wx.OK | wx.ICON_WARNING, self)
            self.recipient_ctrl.SetFocus()
            return

        if not text:
            wx.MessageBox("Digite o texto da mensagem direta.", "Aviso", wx.OK | wx.ICON_WARNING, self)
            self.message_ctrl.SetFocus()
            return

        self.recipient_value = recipient
        self.message_value = text
        self.EndModal(wx.ID_OK)

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        ctrl = event.ControlDown()
        if ctrl and key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_submit(event)
        elif key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()

    def get_data(self) -> tuple[str, str]:
        return self.recipient_value, self.message_value


class SettingsDialog(wx.Dialog):
    """
    Diálogo acessível de configurações do Accessible Timeline.
    Permite configurar a verificação automática de atualizações e preferências do aplicativo.
    """
    def __init__(self, parent: wx.Window):
        super().__init__(
            parent,
            title="Configurações",
            size=(520, 240),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        self._init_ui()
        self.CenterOnParent()

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Grupo Atualizações
        update_box = wx.StaticBox(panel, label="Atualizações do Aplicativo")
        update_sizer = wx.StaticBoxSizer(update_box, wx.VERTICAL)

        self.chk_auto_updates = wx.CheckBox(
            panel,
            label="&Verificar atualizações automaticamente ao iniciar o aplicativo"
        )
        self.chk_auto_updates.SetValue(config_manager.get("check_updates_automatically", True))
        update_sizer.Add(self.chk_auto_updates, 0, wx.ALL, 10)

        sizer.Add(update_sizer, 0, wx.EXPAND | wx.ALL, 12)

        # Botões de Ação
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.save_btn = wx.Button(panel, wx.ID_OK, label="&Salvar")
        self.save_btn.SetDefault()
        btn_sizer.Add(self.save_btn, 0, wx.RIGHT, 10)

        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancelar")
        btn_sizer.Add(cancel_btn, 0)

        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 12)
        panel.SetSizer(sizer)

        self.Bind(wx.EVT_BUTTON, self._on_save, id=wx.ID_OK)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        wx.CallAfter(self.chk_auto_updates.SetFocus)

    def _on_save(self, event):
        auto_check = self.chk_auto_updates.GetValue()
        config_manager.set("check_updates_automatically", auto_check)
        self.EndModal(wx.ID_OK)

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()


class UpdateDownloadDialog(wx.Dialog):
    """
    Diálogo acessível de download e instalação da atualização do Accessible Timeline.
    Exibe barra de progresso, porcentagem e quantidade de megabytes baixados,
    permitindo cancelamento a qualquer momento com Escape ou botão Cancelar.
    """
    def __init__(self, parent: wx.Window, download_url: str, new_version: str):
        super().__init__(
            parent,
            title=f"Baixando Atualização v{new_version}",
            size=(520, 220),
            style=wx.DEFAULT_DIALOG_STYLE
        )
        self.download_url = download_url
        self.new_version = new_version
        self._cancelled = False
        self._download_success = False
        self._target_zip: Optional[str] = None
        self._last_announced_pct = -1

        self._init_ui()
        self.CenterOnParent()
        wx.CallAfter(self._start_download)

    def _init_ui(self):
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.status_label = wx.StaticText(
            panel,
            label=f"Baixando pacote da versão {self.new_version}. Por favor, aguarde..."
        )
        sizer.Add(self.status_label, 0, wx.ALL, 12)

        self.gauge = wx.Gauge(panel, range=100, size=(480, 25))
        sizer.Add(self.gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)

        self.progress_label = wx.StaticText(
            panel,
            label="Conectando aos servidores do GitHub..."
        )
        sizer.Add(self.progress_label, 0, wx.ALL, 12)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.cancel_btn = wx.Button(panel, wx.ID_CANCEL, label="&Cancelar")
        btn_sizer.Add(self.cancel_btn, 0)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 12)

        panel.SetSizer(sizer)

        self.Bind(wx.EVT_BUTTON, self._on_cancel, id=wx.ID_CANCEL)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

    def _start_download(self):
        from src.core.updater import download_update_archive

        self._target_zip = os.path.join(tempfile.gettempdir(), f"AccessibleTimeline_v{self.new_version}.zip")

        def _on_progress(downloaded: int, total: int):
            if self._cancelled:
                return False
            pct = int((downloaded / total) * 100) if total > 0 else 0
            mb_down = downloaded / (1024 * 1024)
            mb_total = total / (1024 * 1024) if total > 0 else 0

            def _update_ui():
                if self._cancelled or not self:
                    return
                self.gauge.SetValue(min(pct, 100))
                self.progress_label.SetLabel(f"{pct}% ({mb_down:.1f} MB de {mb_total:.1f} MB)")
                # Atualiza título periodicamente para leitura discreta de leitores de tela
                if pct // 20 != self._last_announced_pct // 20:
                    self._last_announced_pct = pct
                    self.SetTitle(f"Baixando Atualização v{self.new_version} ({pct}%)")

            wx.CallAfter(_update_ui)
            return True

        def _worker():
            success = download_update_archive(self.download_url, self._target_zip, progress_callback=_on_progress)
            self._download_success = success

            def _finish():
                if self._cancelled:
                    self.EndModal(wx.ID_CANCEL)
                    return
                if success:
                    self.EndModal(wx.ID_OK)
                else:
                    wx.MessageBox(
                        "Falha ao realizar o download da atualização.\nVerifique sua conexão de rede ou tente novamente.",
                        "Erro no Download",
                        wx.OK | wx.ICON_ERROR,
                        self
                    )
                    self.EndModal(wx.ID_CANCEL)

            wx.CallAfter(_finish)

        threading.Thread(target=_worker, daemon=True, name="UpdateDownloadThread").start()

    def _on_cancel(self, event):
        self._cancelled = True
        self.status_label.SetLabel("Cancelando download...")
        self.cancel_btn.Enable(False)

    def _on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._on_cancel(event)
        else:
            event.Skip()

    def get_zip_path(self) -> Optional[str]:
        return self._target_zip if self._download_success else None



