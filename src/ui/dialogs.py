import webbrowser
from typing import List, Optional
import wx
from src.core.models import Post


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

