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
  - **Formatação Limpa**: O arquivo deve conter exclusivamente as seções das versões diretamente (iniciando em `## [X.Y.Z-dev.N]`), sem comentários introdutórios, títulos gerais ou preâmbulos no topo do arquivo.
- **Changelog Público (`CHANGELOG.txt`)**:
  - Voltado aos usuários finais, em formato de texto simples (.txt), com escrita calorosa, clara e amigável para leitores de tela.
  - **REGRA PERMANENTE**: O arquivo `CHANGELOG.txt` **NUNCA** deve ser atualizado automaticamente em tarefas cotidianas.
  - **Gatilho de Atualização**: O `CHANGELOG.txt` só será atualizado quando o usuário der a ordem explícita:
    > *"gere um changelog da versão interna X até a Y com a versão tal"*
  - Nesse momento, e apenas nesse momento, o agente irá consolidar as alterações das versões internas `X` até `Y` sob a versão pública designada pelo usuário.

### 8.3. Padrão Obrigatório de Mensagens de Commit no Git
- A cada commit realizado no repositório Git, a mensagem de commit deve replicar exatamente a entrada correspondente da versão que foi registrada no `CHANGELOG_DEV.md` (incluindo o título da versão interna e o detalhamento dos itens modificados, adicionados, corrigidos ou testados).

---

## 9. Governança de Releases Públicas, CI/CD e Atualizações Automáticas

Este protocolo estabelece o fluxo obrigatório e automatizado para o lançamento de novas versões públicas do **Accessible Timeline**.

### 9.1. Gatilho de Lançamento de Release
O processo de release é estritamente manual e ativado sob comando explícito do usuário, por exemplo:
> *"lance a release da versão 0.2.0"* ou *"crie a release da versão X.Y.Z"*

### 9.2. Protocolo de Execução Pré-Release (Checklist Obrigatório)
Ao receber a ordem de release para a versão `X.Y.Z`, o agente deve executar ordenadamente as seguintes etapas:
1. **Consolidação Bilíngue do Changelog e Documentação (`CHANGELOG.txt` e `README.html`)**:
   - Consolidar as alterações técnicas relevantes para o usuário final acumuladas desde a última release pública até a versão interna vigente.
   - Gerar o `CHANGELOG.txt` estruturado em seções bilíngues: Português ([PT-BR]) e Inglês ([EN-US]).
   - Gerar/atualizar o manual acessível `README.html` em Português e Inglês com tabela completa de atalhos e instruções para leitores de tela.
   - Manter o tom caloroso, limpo e altamente descritivo para leitores de tela NVDA e JAWS.
2. **Sincronização de Metadados de Versão**:
   - Atualizar a constante `__version__ = "X.Y.Z"` em `src/core/version.py`.
   - Garantir que a barra de título da janela principal (`MainWindow`) e o diálogo "Sobre" reflitam a nova versão.
3. **Validação Rigorosa da Suíte de Testes**:
   - Executar todos os testes unitários (`python -m unittest discover tests`). O processo só pode prosseguir se 100% dos testes forem aprovados.
4. **Commit de Release no Git**:
   - Criar o commit de release pública:
     ```powershell
     git add -A
     git commit -m "Release vX.Y.Z"
     ```
5. **Criação de Tag Git Anotada**:
   - Criar a tag correspondente com o prefixo `v`:
     ```powershell
     git tag -a vX.Y.Z -m "Accessible Timeline vX.Y.Z"
     ```
6. **Publicação no Repositório Remoto**:
   - Enviar commits e tags para o GitHub:
     ```powershell
     git push origin main --tags
     ```

### 9.3. Pipeline Automatizado de CI/CD (GitHub Actions)
- O repositório possui o workflow configurado em `.github/workflows/build-release.yml`.
- **Gatilho**: Ao receber o push de uma tag iniciada em `v*` (ex.: `v0.2.0`), o GitHub Actions:
  1. Inicializa um runner Windows x64 limpo (`windows-latest`).
  2. Instala dependências do Python, Playwright Chromium e PyInstaller.
  3. Executa a suíte de testes unitários para verificação em ambiente isolado.
  4. Compila o binário standalone e empacota todos os arquivos de recursos (`sounds/`, `bass.dll`, etc.) em um pacote portátil ZIP (`AccessibleTimeline-vX.Y.Z-windows-x64.zip`).
  5. Cria automaticamente a **Release Oficial no GitHub Releases** associada à tag, anexando o pacote `.zip` e as notas da versão do `CHANGELOG.txt`.

### 9.4. Verificação de Atualizações pelo Próprio Aplicativo (Auto-Updater)
- O módulo `src/core/updater.py` consulta a API pública do GitHub (`/repos/{owner}/{repo}/releases/latest`).
- Na interface gráfica (`MainWindow`):
  - Menu **Ajuda > Verificar Atualizações...**: Compara a versão local em execução com a última tag lançada no GitHub Releases.
  - Se houver versão mais recente: Exibe diálogo acessível anunciando a nova versão e oferece a abertura imediata do link de download no navegador padrão.


