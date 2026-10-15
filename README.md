# Accessible Timeline

Cliente de timeline acessível para pessoas com deficiência visual e usuários de leitores de tela (NVDA e JAWS), inspirado no TWBlue e The Qube.

## Visão Geral (Fase 1)

Nesta primeira fase, o Accessible Timeline implementa o núcleo fundamental de acesso, extração e leitura da timeline do X (antigo Twitter):

1. **Separação estrita entre Leitura e Interação**: O módulo de leitura e parser de dados é desacoplado do ciclo de ações.
2. **Sessão Autenticada e Perfil Persistente**: Utiliza o Chromium real com perfil persistente em `%APPDATA%/AccessibleTimeline/x_profile`, permitindo login manual, 2FA e preservação de cookies.
3. **Interceptação Passiva de Dados**: Observa as respostas GraphQL enviadas pelo X para o próprio navegador (`/HomeTimeline`, etc.), sem modificar as respostas e sem depender de seletores de DOM frágeis.
4. **Interface Nativa Win32 Acessível**: Construída em wxPython com controle nativo (`SysListView32`), proporcionando leitura natural e sem eco pelo NVDA e JAWS.
5. **Preservação de Posição e Deduplicação**: As publicações recebidas são unificadas por ID na memória, preservando a postagem atualmente selecionada mesmo com a chegada de novas postagens no topo da timeline.

---

## Estrutura do Projeto

```
accessible-timeline/
├── run.py                           # Ponto de entrada do aplicativo
├── requirements.txt                 # Dependências (wxPython, playwright)
├── README.md
├── src/
│   ├── core/
│   │   ├── models.py                # Modelos universais: Post, MediaItem
│   │   └── timeline_store.py        # Armazenamento em memória, deduplicação e posição
│   ├── platforms/
│   │   ├── base.py                  # Interfaces abstratas: BaseTimelineReader, BaseActionExecutor
│   │   └── x_twitter/
│   │       ├── parser.py            # Parser GraphQL resiliente
│   │       ├── browser.py           # Gerenciador de ciclo de vida do Chromium
│   │       └── reader.py            # Implementação de BaseTimelineReader para o X
│   └── ui/
│       ├── app.py                   # Classe wx.App e orquestração
│       ├── main_window.py           # Janela acessível com controles nativos Win32
│       └── dialogs.py               # Diálogo acessível para leitura detalhada
└── tests/
    ├── test_parser.py               # Testes unitários do parser GraphQL
    └── test_timeline_store.py       # Testes de deduplicação e preservação de posição
```

---

## Como Executar

### Pré-requisitos
- Python 3.11 ou 3.12 (64-bit) no Windows
- Dependências instaladas:
  ```powershell
  pip install -r requirements.txt
  playwright install chromium
  ```

### Iniciar o Aplicativo
No diretório do projeto, execute:
```powershell
python run.py
```

---

## Guia de Atalhos de Teclado

| Tecla / Atalho | Ação |
| :--- | :--- |
| **Seta para Baixo** | Move o foco para a próxima publicação na lista |
| **Seta para Cima** | Move o foco para a publicação anterior na lista |
| **Enter** | Abre o diálogo com os detalhes completos da publicação selecionada |
| **Escape** | Fecha o diálogo de detalhes e retorna à lista de publicações |
| **F5** | Solicita a atualização da timeline |
| **Ctrl + M** | Carrega mais postagens (rola o navegador) |
| **F12** | Exibe ou oculta a janela do Chromium (útil para login ou verificação) |
| **Alt + F4** | Encerra o aplicativo e o processo do navegador |

---

## Roteiro de Teste com Leitor de Telas (NVDA / JAWS)

1. **Primeiro Acesso e Login**:
   - Inicie o aplicativo com `python run.py`.
   - A janela principal do Accessible Timeline será exibida e a janela do Chromium também será aberta na página do X.
   - Caso não esteja autenticado, use `Alt+Tab` para ir à janela do Chromium e faça o login no X normalmente.
   - Uma vez logado, a timeline do X carregará os dados.
   - Pressione `F12` para ocultar o navegador Chromium e retorne ao Accessible Timeline.
2. **Navegação na Lista**:
   - Pressione `Seta para Baixo` e `Seta para Cima`.
   - O NVDA/JAWS deve anunciar imediatamente o nome do autor, arroba, horário relativo, resumo do texto e contadores de curtidas/reposts.
   - O leitor deve informar a posição na lista (ex: "1 de 20").
3. **Leitura Detalhada**:
   - Pressione `Enter` sobre uma publicação.
   - O foco irá para a caixa de texto multilinha do diálogo.
   - Use as setas para ler linha por linha, caractere por caractere ou `Ctrl+C` no botão Copiar.
   - Pressione `Escape` para retornar exatamente ao mesmo item na lista.
4. **Atualização**:
   - Pressione `F5` para recarregar a timeline e verifique se novos itens são incorporados no topo sem mudar a publicação que você estava lendo.
