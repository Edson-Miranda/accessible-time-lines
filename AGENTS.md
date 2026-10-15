# Diretrizes de Desenvolvimento e Governança Técnica (AGENTS.md)
# Projeto: Accessible Timeline

Este documento estabelece as regras, padrões arquiteturais e diretrizes permanentes que devem ser rigorosamente seguidos por qualquer agente de inteligência artificial ou desenvolvedor que atue no projeto **Accessible Timeline**.

---

## 1. Visão Geral e Filosofia do Projeto

O **Accessible Timeline** é um cliente de redes sociais e plataformas de conteúdo concebido especificamente para pessoas com deficiência visual, com foco prioritário em usuários dos leitores de tela **NVDA** e **JAWS**. Inspirado no legado de clientes consagrados como **TWBlue** e **The Qube**, o objetivo principal é resgatar a experiência de navegação rápida, linear, desobstruída e totalmente operável por teclado, eliminando o atrito das interfaces web modernas.

A acessibilidade não é uma funcionalidade complementar; ela é o alicerce fundamental de todas as decisões técnicas e de design.

---

## 2. Estado Atual do Projeto

- **Fase Vigente**: **Fase 1 - Núcleo de Leitura e Validação da Timeline (X/Twitter)**.
- **Escopo da Fase 1**:
  - Inicialização do navegador com sessão autenticada persistente.
  - Interceptação passiva e estruturação de postagens do X via GraphQL.
  - Apresentação em lista nativa acessível (`wx.ListCtrl` / Win32).
  - Navegação fluida por setas com leitura limpa no NVDA e JAWS.
  - Diálogo acessível para visualização de texto completo e links.
- **Desenvolvimento Incremental Estrito**:
  - É expressamente proibido adiantar funcionalidades de fases futuras (ex.: curtidas, reposts, publicação de tweets, atalhos globais de segundo plano ou novas plataformas) sem solicitação explícita do usuário.

---

## 3. Diretrizes Fundamentais de Acessibilidade

### 3.1. Compatibilidade com Leitores de Tela (NVDA e JAWS)
- **Controles Nativos em Primeiro Lugar**: Toda interface gráfica no modo visível deve utilizar controles nativos do Windows (Win32 / UI Automation) disponibilizados via `wxPython` (como `wx.ListCtrl`, `wx.TextCtrl`, botões padrão). Leitores de tela possuem suporte maduro e otimizado para esses controles.
- **Prevenção de Anúncios Duplicados (Double Speech)**:
  - No **modo janela visível**, nunca envie comandos diretos de fala para o sintetizador do NVDA/JAWS ao navegar em listas ou controles focáveis. O leitor de tela deve anunciar o controle de forma natural através dos eventos de acessibilidade do sistema operacional.
  - A fala direta (`nvdaController_speakText`, `SayString` do JAWS) é reservada exclusivamente para o **modo em segundo plano** (fases futuras), quando o foco da área de trabalho não puder ser alterado.
- **Preservação Previsível do Foco**:
  - Nenhuma operação de atualização, sincronização em segundo plano ou resposta assíncrona do navegador pode roubar ou deslocar inesperadamente o foco do teclado.
  - Diálogos secundários (como exibição de detalhes) devem restaurar o foco para o elemento original de origem ao serem fechados.

### 3.2. Operabilidade Completa por Teclado
- Qualquer função, painel ou ação do aplicativo deve ser 100% operável via teclado.
- Atalhos de teclado mnemônicos e universais:
  - Navegação em listas: `Setas Cima / Baixo`, `Home`, `End`, `PageUp`, `PageDown`.
  - Abertura de itens: `Enter` ou `Espaço`.
  - Fechamento de telas e cancelamento: `Escape`.
  - Atualização: `F5`.

---

## 4. Separação Arquitetural e Modularidade

O projeto adota separação estrita de responsabilidades em camadas desacopladas:

1. **Camada de Modelos e Estado (`src/core/`)**:
   - `models.py`: Entidades universais agnósticas de serviço (`Post`, `MediaItem`, `User`). Nenhuma entidade desta camada pode importar detalhes do navegador ou da interface gráfica.
   - `timeline_store.py`: Armazenamento em memória thread-safe. Realiza deduplicação estrita por identificador único (`id`) e mantém o ponteiro do cursor de leitura intacto durante inserções no topo da lista.
2. **Camada de Plataformas (`src/platforms/`)**:
   - `base.py`: Contratos abstratos obrigatórios (`BaseTimelineReader` e `BaseActionExecutor`).
   - **Regra de Isolamento**: O componente de **obtenção e parsing de postagens** (`reader.py` / `parser.py`) deve ser completamente independente do componente de **execução de ações** (`executor.py`). Mudanças na API ou layout de um serviço não devem impactar a camada de ações nem a interface acessível.
3. **Camada de Automação e Navegador (`src/platforms/x_twitter/browser.py`)**:
   - Isolamento de processos: O navegador real (Playwright Chromium) roda em thread dedicada de segundo plano com fila de comandos assíncrona (`queue.Queue`), impedindo qualquer congelamento da interface gráfica.
   - Comunicação com a UI sempre despachada de forma thread-safe via `wx.CallAfter`.
4. **Camada de Interface Gráfica (`src/ui/`)**:
   - Responsável exclusiva pela renderização visual, eventos de teclado e diálogo com o usuário.

---

## 5. Integridade, Sessões e Regras das Plataformas

### 5.1. Persistência de Autenticação e Modo Oculto Permanente
- O navegador deve utilizar diretório persistente de perfil de usuário (`user_data_dir`) localizado no padrão do sistema operacional (`%APPDATA%/AccessibleTimeline/x_profile`).
- Cookies, tokens de sessão, credenciais salvas e verificações em duas etapas (2FA) devem ser preservados entre reinicializações.
- Uma vez autenticado (verificado via cookies de sessão válidos), o navegador deve rodar estritamente em segundo plano/headless (`headless=True`), sem exibir qualquer janela visível, ícone na barra de tarefas ou interferência visual. Uma vez logado, a janela do navegador não deve mais ser reexibida.

### 5.2. Proibição de Práticas Indevidas
- **Sem Camuflagem ou Evasão**: É expressamente proibido implementar scripts de camuflagem de bot (como `playwright_stealth`), hacks para burlar Cloudflare/Arkose, ou mecanismos para contornar verificações de segurança dos serviços.
- **Interação 1:1 Baseada em Intenção Humana**: Nenhuma ação em lote, scraping massivo ou comportamento agressivo automatizado deve ser inserido. O aplicativo atua como facilitador de acessibilidade para ações pontuais comandadas pelo usuário.
- Se uma plataforma impuser restrições técnicas que impeçam determinada funcionalidade por métodos legítimos, o agente deve relatar a limitação e propor alternativas antes de qualquer alteração de código.

---

## 6. Resiliência, Tratamento de Erros e Desconexão

- **Falhas de Conexão**: O aplicativo não deve travar nem perder postagens em memória se a conexão de internet cair ou se o carregamento demorar.
- **Barra de Status Informativa**: Mensagens de estado claras e audíveis devem ser publicadas na barra de status da janela (ex.: *"Acessando o serviço..."*, *"Pronto. 20 publicações carregadas"*, *"Falha ao conectar"*).
- **Encerramento Limpo**: Ao fechar a aplicação (`EVT_CLOSE`), todos os subprocessos do navegador, threads de trabalho e ouvintes devem ser desvinculados e encerrados ordenadamente sem processos zumbis em memória.

---

## 7. Políticas de Modificação de Código e Qualidade

Qualquer modificação no repositório deve respeitar os seguintes princípios:

1. **Preservação de Funcionalidades Existentes**:
   - É estritamente proibido quebrar ou remover código existente que já foi validado, a menos que haja solicitação explícita de refatoração pelo usuário.
2. **Proibição de Funcionalidades Não Solicitadas**:
   - Não crie abstrações desnecessárias, botões extras ou atalhos que não tenham sido aprovados no planejamento da fase atual.
3. **Testes de Regressão Obrigatórios**:
   - Toda alteração nas regras de parsing (`tests/test_parser.py`) ou no gerenciamento de memória e cursor (`tests/test_timeline_store.py`) deve ser acompanhada da execução e validação da suíte de testes unitários:
     ```powershell
     python -m unittest discover tests
     ```
   - Novos casos de borda identificados devem ser convertidos em novos testes unitários.
4. **Legibilidade e Documentação**:
   - Código escrito em Python limpo (PEP 8), com tipagem estática através de type hints (`typing`), docstrings explicativas e logs em pontos críticos de integração.

---

## 8. Governança de Versionamento e Changelogs

O projeto adota uma separação rigorosa entre **versões internas de desenvolvimento** e **versões públicas para usuários**:

### 8.1. Dois Níveis de Versão
- **Versão Interna (Desenvolvimento)**:
  - Formato: `X.Y.Z-dev.N` (ex.: `0.1.0-dev.1`, `0.1.0-dev.2`).
  - Incrementada a cada ciclo técnico, conjunto de alterações ou refatoração no repositório.
- **Versão Externa / Pública**:
  - Inicia em `0.1.0A` e segue versionamento semântico com sufixos alfabéticos de pré-lançamento/alfa/beta.
  - Representa versões estáveis ou de teste disponibilizadas para os usuários.

### 8.2. Regra Estrita de Atualização dos Changelogs
- **Changelog de Desenvolvimento (`CHANGELOG_DEV.md`)**:
  - Documenta alterações técnicas detalhadas, refatorações, adições de módulos e testes.
  - Atualizado a cada avanço técnico ou versão interna.
- **Changelog Público (`CHANGELOG.txt`)**:
  - Voltado aos usuários finais, em formato de texto simples (.txt), com escrita calorosa, clara e amigável para leitores de tela.
  - **REGRA PERMANENTE**: O arquivo `CHANGELOG.txt` **NUNCA** deve ser atualizado automaticamente em tarefas cotidianas.
  - **Gatilho de Atualização**: O `CHANGELOG.txt` só será atualizado quando o usuário der a ordem explícita:
    > *"gere um changelog da versão interna X até a Y com a versão tal"*
  - Nesse momento, e apenas nesse momento, o agente irá consolidar as alterações das versões internas `X` até `Y` sob a versão pública designada pelo usuário.

