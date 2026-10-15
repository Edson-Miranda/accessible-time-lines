# Changelog de Desenvolvimento (Interno) - Accessible Timeline

Este documento registra todas as alterações técnicas, refatorações e adições internas da base de código, organizadas por versões internas.

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
