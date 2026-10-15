"""
Diálogos acessíveis para o Accessible Timeline.
Projetados com foco prioritário em leitores de tela (NVDA e JAWS).
"""

import wx
from src.core.models import Post


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

        if self.post.url:
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
        if self.post.url:
            import webbrowser
            webbrowser.open(self.post.url)

    def _on_char_hook(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
        else:
            event.Skip()
