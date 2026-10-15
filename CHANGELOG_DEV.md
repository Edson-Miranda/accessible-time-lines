# Changelog de Desenvolvimento (Interno) - Accessible Timeline

Este documento registra todas as alterações técnicas, refatorações e adições internas da base de código, organizadas por versões internas.

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
