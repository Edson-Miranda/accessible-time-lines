## [0.1.0-dev.8] - 2026-10-16

### Adicionado
- **Camada de Execução de Ações (`src/platforms/x_twitter/executor.py`)**:
  - Implementação completa de `XActionExecutor` herdando de `BaseActionExecutor` (`src/platforms/base.py`).
  - Métodos desacoplados e resilientes para:
    - Postar novo tweet (`create_post`)
    - Responder publicação (`reply_to_post`)
    - Repostar / Retweet simples (`retweet_post`)
    - Repostar com comentário / Citar (`quote_post`)
    - Curtir (`like_post`) e Descurtir (`unlike_post`)
    - Enviar mensagem direta privada (`send_dm`)
  - Suporte a despacho assíncrono thread-safe (`run_async`) com retorno para a thread principal de UI via `wx.CallAfter`.
- **Automação Humana 1:1 no Chromium (`src/platforms/x_twitter/browser.py`)**:
  - Métodos dedicados `_do_create_post`, `_do_reply_to_post`, `_do_retweet_post`, `_do_quote_post`, `_do_like_post`, `_do_unlike_post` e `_do_send_dm` executados em segundo plano com relatórios de status em tempo real.
- **Diálogos Acessíveis Inspirados no TWBlue (`src/ui/dialogs.py`)**:
  - `NewPostDialog`: Composição de tweet com contagem dinâmica regressiva de 280 caracteres e atalho `Ctrl+Enter` para envio direto.
  - `ReplyDialog`: Resposta com consulta acessível do tweet original e atalho `Ctrl+Enter`.
  - `QuoteDialog`: Citação com campo de comentário e atalho `Ctrl+Enter`.
  - `RetweetChoiceDialog`: Diálogo acessível para escolha rápida entre repostar direto ou citar.
  - `SendDMDialog`: Diálogo para mensagem direta com campos de destinatário e mensagem privada.
- **Menu e Atalhos Rápidos na Interface Principal (`src/ui/main_window.py`)**:
  - Novo menu **Ações** no MenuBar.
  - Atalhos operáveis por teclado:
    - `Ctrl + N`: Nova publicação.
    - `Ctrl + R`: Responder.
    - `Ctrl + Shift + R`: Repostar / Retweet.
    - `Ctrl + Shift + C`: Citar com comentário.
    - `Ctrl + L` ou tecla `L`: Curtir / Descurtir.
    - `Ctrl + D`: Enviar Mensagem Direta.
- **Configuração de Ambiente**:
  - Adicionado `tw blue/` e variações ao `.gitignore`.

### Testes
- Adicionados 7 novos testes unitários em `tests/test_executor.py` cobrindo todas as ações da camada de execução (`create_post`, `reply_to_post`, `retweet_post`, `quote_post`, `like_post`, `unlike_post`, `send_dm`). Suíte completa com 14 testes passando.

---

## [0.1.0-dev.7] - 2026-10-16

### Adicionado
- **Abertura Rápida de Links com `Control + Enter`**:
  - Implementado atalho `Ctrl + Enter` (e acelerador no menu Timeline) para abrir links da publicação selecionada no navegador padrão do sistema.
  - Implementado `SelectLinkDialog` com `wx.ComboBox` nativo acessível (`SysComboBox32` em modo `wx.CB_READONLY`), permitindo ao usuário escolher facilmente com setas Cima/Baixo qual link abrir quando o post possui mais de um link.
  - Adicionado método `get_all_links()` no modelo `Post`, consolidando URLs de entidades expandidas, links contidos no texto, mídias anexadas e a própria URL da postagem no X, com deduplicação rigorosa.
  - Diálogo de detalhes (`PostDetailsDialog`) atualizado para também utilizar seleção múltipla de links quando aplicável.

### Corrigido
- **Leitura do Post Completo na Lista pelo Leitor de Tela**:
  - Removido o truncamento de 160 caracteres em `Post.to_accessible_summary()`. Agora o texto completo da publicação é disponibilizado na lista nativa `wx.ListCtrl`, permitindo ao usuário do NVDA e JAWS ouvir a mensagem na íntegra simplesmente navegando com as setas Cima e Baixo, sem necessidade de abrir a tela de detalhes apenas para ler o restante do post.
- **Pré-carregamento Confiável de Todas as Guias na Inicialização**:
  - Implementada rotina `_preload_all_tabs` no `XBrowserManager`, que visita as guias ("Para você", "Seguindo" e "Menções/Notificações") ao iniciar o programa, capturando os conteúdos para cada uma das listas antes de retornar à timeline principal.
  - Mensagens informativas passo a passo publicadas na barra de status durante o carregamento inicial ("Carregando fluxo Para você...", "Carregando fluxo Seguindo...", "Carregando Menções e Notificações...", "Pronto. Publicações carregadas.").
  - Alternância de abas reforçada com busca nativa de locators do Playwright (`_click_tab_by_name`) com fallback para script JS, garantindo o disparo confiável de eventos de clique nos componentes React do X.
  - Ampliada a interceptação de endpoints de rede para cobrir toda a árvore `/i/api/`, suportando GraphQL, API v2 e estruturas com `globalObjects`.
- **Seleção Inicial na Lista**:
  - `MainWindow._sync_list` atualizado para garantir seleção e foco automático no primeiro item (`idx = 0`) assim que as primeiras postagens chegam.

### Testes
- Adicionados testes unitários em `tests/test_parser.py`:
  - `test_post_full_text_not_truncated_in_summary`: validação de que textos com mais de 200 caracteres não são truncados no resumo da lista.
  - `test_post_get_all_links`: validação da extração e integridade de múltiplos links (texto, entidades, mídia e post).
  - `test_parse_global_objects_notifications`: validação da extração de postagens em estruturas `globalObjects`.

---

## [0.1.0-dev.6] - 2026-10-15

### Modificado
- **Execução Oculta Permanente do Navegador (Headless)**:
  - O Chromium agora roda em modo 100% headless (`headless=True`) assim que a sessão é confirmada como autenticada (verificada via leitura segura do banco SQLite de cookies em `Default/Network/Cookies` procurando por `auth_token`).
  - Nenhuma janela do navegador é criada ou exibida após o login, eliminando janelas visíveis, ícones na barra de tarefas e interferências de foco com leitores de tela.
  - A janela do navegador só é inicializada visível caso o usuário ainda não esteja autenticado no perfil local, garantindo que o login inicial e 2FA possam ser feitos normalmente.
- **Remoção Definitiva do Atalho F11 e Menus do Navegador**:
  - Remoção do atalho `F11` (que no Chromium causava alternância nativa de tela cheia em vez de ocultação).
  - Remoção de todos os métodos e comandos de alternância de visibilidade do navegador na interface (`MainWindow`), leitor (`XTimelineReader`) e gerenciador (`XBrowserManager`).
  - Atualização correspondente no `AGENTS.md` e `README.md`.

---

## [0.1.0-dev.5] - 2026-10-15

### Adicionado
- **Layout Clássico em Árvore (`wx.TreeCtrl` / `SysTreeView32`)**:
  - Transição do modelo de guias para o layout de árvore clássico do TWBlue e The Qube.
  - Painel esquerdo com Árvore nativa acessível contendo o nó da conta (com expansão/recolhimento) e seus respectivos fluxos como nós filhos:
    - **Para você** (feed algorítmico)
    - **Seguindo** (timeline cronológica)
    - **Menções (Notificações)**
    - **Mensagens diretas**
  - Painel direito com Lista nativa (`wx.ListCtrl`) exibindo as publicações do fluxo ativo.
- **Navegação Bidirecional por Teclado**:
  - `Tab` (na árvore): Move o foco diretamente para a lista de postagens do fluxo ativo.
  - `Shift + Tab` (na lista): Retorna o foco diretamente para o item selecionado na árvore.
  - Setas Direita/Esquerda (na árvore): Expande ou recolhe o nó da conta.
  - Atalhos globais na janela: `Control + Windows + Setas Cima/Baixo/Esquerda/Direita` e `Ctrl + Tab` para ciclar entre os fluxos da árvore de qualquer lugar.
- **Detecção de Nome da Conta**:
  - O navegador agora detecta o nome de exibição e @handle da conta conectada via DOM do X e atualiza dinamicamente o nó raiz da árvore (ex.: *"Nome (@usuario)"*).
- **Roteamento de Múltiplos Fluxos**:
  - Armazenamento desacoplado em `TimelineStore` dedicados para cada fluxo (`for_you`, `following`, `mentions`, `dms`).

---

## [0.1.0-dev.4] - 2026-10-14

### Corrigido
- **Ocultação e Visibilidade do Navegador via CDP**:
  - Migração do controle de visibilidade da janela do Chromium para o Chrome DevTools Protocol (`Browser.setWindowBounds` com `windowState: "minimized"` e `"normal"`).
  - Eliminação definitiva de falhas causadas por tipos de 32-bit em enumerações Win32 x64 e títulos variáveis da página. O navegador agora minimiza/oculta imediatamente na inicialização.
- **Alternância de Guias no Navegador ('Para você' e 'Seguindo')**:
  - Implementação de injeção de script JavaScript direto no DOM para alternância de abas, localizando os elementos pelos rótulos textuais ("Para você" / "For you" e "Seguindo" / "Following").
  - Elimina bloqueios causados por rolagem da página ou verificações de estabilidade visual do Playwright, garantindo que o clique na aba do site original seja sempre executado.
- **Pré-carregamento dos Dois Feeds na Inicialização**:
  - O navegador agora percorre as abas na inicialização para disparar as requisições `HomeTimeline` e `HomeLatestTimeline`, garantindo que ambas as guias tenham postagens carregadas desde o primeiro momento.
- **Prevenção de Chamadas Duplicadas**:
  - Refatoração de `MainWindow._toggle_tab` para delegar a notificação ao manipulador de eventos de página, evitando requisições duplicadas em sequência.

---

## [0.1.0-dev.3] - 2026-10-14

### Adicionado
- **Suporte a Múltiplas Guias ('Para você' e 'Seguindo')**:
  - Implementação de controle de abas nativo Win32 (`wx.Notebook` / `SysTabControl32`) dividindo as postagens entre os feeds **Para você** (Home) e **Seguindo** (Following), inspirado no TWBlue.
  - Cada guia possui sua própria lista independente (`wx.ListCtrl`) e seu próprio `TimelineStore` isolado, garantindo posições de leitura e históricos separados.
  - Navegação fluida via teclado:
    - `Shift + Tab` a partir da lista move o foco para o cabeçalho de guias (`SysTabControl32`), onde o leitor de telas anuncia a guia selecionada e sua posição (ex.: "Para você guia selecionada 1 de 2"). Setas Esquerda/Direita trocam a guia e `Tab` retorna à lista correspondente.
    - Atalho direto `Control + Windows + Seta Direita` e `Control + Windows + Seta Esquerda` para alternância imediata de qualquer lugar.
    - Suporte aos atalhos `Ctrl + Tab` e `Ctrl + Shift + Tab`.
- **Sincronização com o Navegador**:
  - `XBrowserManager` e `XTimelineReader` agora identificam a origem das respostas da API do X (`HomeTimeline` para 'Para você' e `HomeLatestTimeline` para 'Seguindo').
  - Método `switch_feed_tab` clica na aba correspondente no site do X (`role="tab"`), acionando o carregamento dinâmico do feed solicitado.
  - Atualização com `F5` agora recarrega a guia ativa no momento.

---

## [0.1.0-dev.2] - 2026-10-14

### Corrigido
- **Controle de Visibilidade do Navegador**:
  - Correção na localização de janelas Win32 do Chromium (`Chrome_WidgetWin_1`), permitindo ocultar e reexibir a janela do navegador de forma confiável via `F11`.
  - Implementação de detecção automática de login (`auth_token`): ao concluir o login, a janela do Chromium é ocultada automaticamente para que o usuário permaneça focado na interface acessível.
  - Se o usuário já estiver autenticado em execuções posteriores, o navegador inicia diretamente oculto.
- **Extração e Atualização da Timeline**:
  - Correção no `parser.py` para compatibilidade com o esquema recente de respostas GraphQL do X, onde `name` e `screen_name` dos autores residem em `user_results.result.core`.
  - Interceptação de respostas de rede transferida para o nível do `BrowserContext`, garantindo que requisições de qualquer aba ou fluxo de redirecionamento sejam capturadas.
  - Gatilho automático de carregamento da home caso o login seja concluído sem postagens carregadas anteriormente.
- **Testes**:
  - Adição do teste unitário `test_parse_modern_graphql_with_core_user` em `tests/test_parser.py`.

---

## [0.1.0-dev.1] - 2026-10-14

### Adicionado
- **Estrutura Base do Projeto**:
  - Arquitetura desacoplada em `src/core`, `src/platforms` e `src/ui`.
  - Configuração de dependências em `requirements.txt` (`wxPython` e `playwright`).
- **Núcleo de Dados (`src/core/`)**:
  - `models.py`: Classes `Post` e `MediaItem` universais e agnósticas de plataforma, com métodos `to_accessible_summary()` e `to_accessible_full()`.
  - `timeline_store.py`: Armazenamento em memória thread-safe com deduplicação por ID e recálculo dinâmico de índice para preservação do cursor de leitura durante inserções no topo.
- **Camada de Plataformas (`src/platforms/`)**:
  - `base.py`: Contratos abstratos `BaseTimelineReader` e `BaseActionExecutor`, garantindo a separação estrita entre leitura de dados e ações de escrita.
  - `x_twitter/parser.py`: Parser funcional e recursivo para respostas JSON da API GraphQL do X (`/HomeTimeline`, etc.), com suporte a tweets comuns, retweets, replies e mídias anexadas.
  - `x_twitter/browser.py`: Gerenciador de ciclo de vida do Chromium via Playwright com perfil persistente (`user_data_dir`), execução em thread dedicada (`XBrowserWorker`), fila de comandos thread-safe e controle de visibilidade Win32 (`ShowWindow`).
  - `x_twitter/reader.py`: Implementação concreta de `BaseTimelineReader` para o X.
- **Interface Gráfica Acessível (`src/ui/`)**:
  - `main_window.py`: Janela principal com controle nativo Win32 (`wx.ListCtrl` no modo relatório de coluna única), barra de status e atalhos de teclado (`Setas`, `Enter`, `F5`, `F11`, `Ctrl+M`).
  - `dialogs.py`: `PostDetailsDialog` com caixa de texto acessível somente-leitura multilinha (`wx.TextCtrl`) para leitura detalhada e cópia de conteúdo.
  - `app.py`: Orquestrador `wx.App` gerenciando o ciclo de vida e despacho de eventos via `wx.CallAfter`.
- **Governança e Testes**:
  - `AGENTS.md`: Diretrizes permanentes de acessibilidade, arquitetura, versionamento e regras de desenvolvimento.
  - `tests/test_parser.py`: Testes unitários automatizados para o parser GraphQL do X.
  - `tests/test_timeline_store.py`: Testes unitários para deduplicação e preservação do índice de seleção no store.
