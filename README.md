# Accessible Timeline

Desenvolvido por **TechTales Entertainment** ([https://techtales.com.br](https://techtales.com.br))

Cliente de timeline acessível para pessoas com deficiência visual e usuários de leitores de tela (NVDA e JAWS), inspirado no legado de clientes consagrados como **TWBlue** e **The Qube**.

Seja muito bem-vindo ao Accessible Timeline! Este projeto nasceu para resgatar a facilidade, a agilidade e a independência que tínhamos com clientes clássicos de redes sociais. Nosso compromisso é entregar uma experiência de navegação rápida, linear e desobstruída, eliminando toda a sobrecarga e o atrito das interfaces web modernas.

---

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
├── README.md                        # Apresentação do projeto e guia de uso
├── CHANGELOG.txt                    # Histórico de alterações voltado aos usuários
├── CHANGELOG_DEV.md                 # Histórico de desenvolvimento interno
├── AGENTS.md                        # Diretrizes permanentes de governança e acessibilidade
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
| **Tab / Shift + Tab** | Alterna o foco entre a **Árvore de fluxos** (esquerda) e a **Lista de postagens** (direita) |
| **Setas Direita / Esquerda** | Na Árvore, expande ou recolhe o nó da conta |
| **Setas Cima / Baixo (na Árvore)** | Navega entre os fluxos: Para você, Seguindo, Menções (Notificações) e Mensagens diretas |
| **Ctrl + Win + Setas Cima / Baixo** | Alterna rapidamente entre os fluxos da Árvore de qualquer lugar |
| **Setas Cima / Baixo (na Lista)** | Navega entre as publicações do fluxo ativo |
| **Enter (na Lista)** | Abre o diálogo com os detalhes completos da publicação selecionada |
| **Escape** | Fecha o diálogo de detalhes e retorna à lista de publicações |
| **F5** | Solicita a atualização do fluxo ativo no momento |
| **Ctrl + M** | Carrega mais postagens no fluxo ativo (rola o navegador) |
| **Alt + F4** | Encerra o aplicativo e o processo do navegador |

---

## Roteiro de Teste com Leitor de Telas (NVDA / JAWS)

1. **Primeiro Acesso e Login**:
   - Se você já estiver logado, o navegador executará silenciosamente em segundo plano (modo 100% invisível/headless), sem abrir qualquer janela ou ícone na barra de tarefas.
   - Caso seja a primeira execução sem login prévio, a janela do Chromium abrirá automaticamente para que você realize o login e o 2FA no X.
   - Assim que o login for concluído, as timelines serão carregadas e, a partir de então, o navegador permanecerá permanentemente oculto em segundo plano.
2. **Navegação na Árvore e Lista**:
   - Pressione `Tab` para alternar entre a Árvore de fluxos (esquerda) e a Lista de publicações (direita).
   - Na lista, use `Seta para Baixo` e `Seta para Cima`.
   - O NVDA/JAWS anunciará o autor, arroba, horário relativo, resumo do texto e métricas de cada postagem.
   - O leitor deve informar a posição na lista (ex: "1 de 20").
3. **Leitura Detalhada**:
   - Pressione `Enter` sobre uma publicação.
   - O foco irá para a caixa de texto multilinha do diálogo.
   - Use as setas para ler linha por linha, caractere por caractere ou `Ctrl+C` no botão Copiar.
   - Pressione `Escape` para retornar exatamente ao mesmo item na lista.
4. **Atualização**:
   - Pressione `F5` para recarregar a timeline e verifique se novos itens são incorporados no topo sem mudar a publicação que você estava lendo.

---

Muito obrigado por fazer parte deste início! Seu retorno e suas impressões de uso são fundamentais para construirmos juntos o melhor cliente acessível possível.
