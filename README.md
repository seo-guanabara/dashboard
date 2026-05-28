# SEO Command Center · Grupo Guanabara

Dashboard de monitoramento orgânico e visibilidade em IA para **viajeguanabara.com.br** e marcas associadas.

**🔗 [seo-guanabara.github.io/dashboard](https://seo-guanabara.github.io/dashboard)**

---

## Visão geral

Painel executivo unificado que consolida dados de múltiplas fontes — Google Analytics 4, Search Console, Semrush e GTmetrix — em uma interface de leitura rápida atualizada diariamente de forma automática.

```
GA4 API (OAuth)  ──┐
GSC CSV          ──┼──► GitHub Actions ──► data.json ──► Dashboard (GitHub Pages)
Semrush API      ──┤
WordPress API    ──┘
```

---

## Funcionalidades

### Big Numbers executivos
| Indicador | Fonte | Comportamento |
|---|---|---|
| Sessões SEO | GA4 API | Dinâmico com período selecionado |
| Receita SEO | GA4 API | Dinâmico com período selecionado |
| Receita YTD | GA4 + CSV | Sempre YoY vs mesmo período 2025 |
| Taxa de Conversão | GA4 API | Transações / Sessões × 100 |
| Share Orgânico | GA4 API | Sessões SEO / Total sessões |
| Impressões SERP | GSC (6 props) | Soma todas as propriedades |

### Filtro de tráfego SEO
Segmenta automaticamente 16 origens orgânicas + LLMs:
- **Busca orgânica:** Google, Bing, DuckDuckGo, Yahoo, Yandex, Ecosia
- **LLMs:** ChatGPT, Gemini, Perplexity, Copilot, Claude.ai, Meta AI

### Seletor de período
- **Padrão:** MTD (1º do mês → último domingo)
- **Presets:** 7 dias · MTD · 30 dias · Mês passado · YTD · Ano passado
- **Comparação:** período paralelo com presets dedicados + delta automático (▲▼)
- **Referência de corte:** sempre último domingo — nunca dados parciais de semana

### Seções do dashboard

| Seção | Dados |
|---|---|
| Google Analytics | Share por canal · Orgânico vs LLMs · Top origens SEO · Top rotas · KPIs detalhados |
| Search Console Geral | Gráfico cliques × impressões · Top queries · Top páginas |
| Indexação & Backlinks | URLs indexadas · Links externos · Viações top páginas |
| Core Web Vitals & GTmetrix | Issues mobile · Performance por layout |
| Semrush | Distribuição de ranking · SERP features · AI Visibility · Competidores |
| Screaming Frog | Issues de crawl · Comparação vs concorrentes |
| Iniciativas SEO | Roadmap Q2/Q3 2026 com status por iniciativa |
| Projeções 2026 | 3 cenários (Estabilização · Ganho Leve · Agressivo) |

### Abas de propriedades
- **Principal** — viajeguanabara.com.br
- **Blog** — blog.viajeguanabara.com.br · artigos WP · dados orgânicos
- **Viva Fidelidade** — vivafidelidade.com.br · cadastros (sign_up) · site + blog

---

## Integrações

| Fonte | Status | Método | Frequência |
|---|---|---|---|
| GA4 Principal (326912205) | ✅ Live | OAuth 2.0 | Diário |
| GA4 Blog (359547158) | ✅ Live | OAuth 2.0 | Diário |
| GA4 Viva Site (408616783) | ✅ Live | OAuth 2.0 | Diário |
| GA4 Viva Blog (394575329) | ✅ Live | OAuth 2.0 | Diário |
| GSC viajeguanabara.com.br | ✅ Live | CSV | Sob demanda |
| GSC novo · www · mkt · destinos · blog | ✅ Live | CSV | Sob demanda |
| GSC Viva site + blog | ✅ Live | CSV | Sob demanda |
| Semrush domain_rank | ✅ Live | API | Diário |
| Semrush domain_organic | ✅ Live | API | Mensal (dia 1) |
| GTmetrix | ✅ Live | API | Diário |
| WordPress Blog | ✅ Live | REST API pública | Diário |
| YouTube | ⏳ Pendente | — | — |
| Play Console | ⏳ Pendente | — | — |

> **Semrush:** `domain_organic` é executado apenas no dia 1 de cada mês para preservar o limite de 50.000 unidades/mês (custo: ~10.000 unidades/relatório).

---

## Estrutura de arquivos

```
dashboard/
├── index.html              # Dashboard (SPA — HTML/CSS/JS puro)
├── data.json               # Gerado automaticamente pelo workflow
│
├── ga4/
│   ├── seo_traffic.csv     # Tráfego SEO filtrado (16 origens)
│   ├── all_channels.csv    # Todos os canais com transações
│   ├── transactions.csv    # Transações por origem/mídia
│   ├── routes.csv          # Páginas /onibus/ (rotas)
│   ├── carriers.csv        # Todas as URLs (filtro por viação no script)
│   └── ytd_yoy.csv         # YTD 2026 + YTD 2025 (dois blocos no CSV)
│
├── gsc/
│   ├── Gráfico.csv         # Performance diária (base do filtro de período)
│   ├── Consultas.csv       # Top queries
│   ├── Páginas.csv         # Top páginas
│   ├── Latest_links.csv    # Backlinks externos
│   ├── grafico_novo.csv    # novo.viajeguanabara.com.br
│   ├── grafico_www.csv     # www.viajeguanabara.com.br
│   ├── grafico_mkt.csv     # mkt.viajeguanabara.com.br
│   ├── grafico_destinos.csv
│   ├── grafico_blog.csv
│   ├── coverage/           # Indexação (Gráfico + Tabela)
│   └── cwv/                # Core Web Vitals (Gráfico + Tabela)
│
├── ga4_blog/
│   └── seo_traffic.csv     # Fallback CSV para blog
│
├── viva/
│   ├── ga4_seo_traffic.csv # Fallback CSV para Viva
│   ├── ga4_all_channels.csv
│   └── gsc/
│       ├── site/           # GSC vivafidelidade.com.br
│       └── blog/           # GSC blog.vivafidelidade.com.br
│
└── scripts/
    ├── fetch_data.py        # Script de coleta de dados
    └── requirements.txt
```

---

## Como atualizar manualmente

### Rodar o workflow
**Actions → Fetch SEO Data → Run workflow**

### Atualizar CSVs do GSC
Exportar do Search Console e substituir os arquivos na pasta `gsc/`:
- **Performance → Exportar → Gráfico** → `Gráfico.csv`
- **Performance → Exportar → Consultas** → `Consultas.csv`
- **Performance → Exportar → Páginas** → `Páginas.csv`
- **Links → Exportar links externos recentes** → `Latest_links.csv`

### Atualizar YTD YoY
Exportar do GA4 com comparação de períodos ativada:
- Período atual: **01/01/2026 → último domingo**
- Comparação: **01/01/2025 → mesmo domingo de 2025**
- Salvar como `ga4/ytd_yoy.csv`

---

## Configuração

### Secrets do GitHub

| Secret | Descrição |
|---|---|
| `GA4_OAUTH_CLIENT_ID` | OAuth 2.0 Client ID (Web App) |
| `GA4_OAUTH_CLIENT_SECRET` | OAuth 2.0 Client Secret |
| `GA4_OAUTH_REFRESH_TOKEN` | Refresh token gerado via OAuth Playground |
| `SEMRUSH_API_KEY` | Chave da API Semrush |
| `GTMETRIX_API_KEY` | Chave da API GTmetrix |
| `WORKLOAD_IDENTITY_PROVIDER` | Workload Identity para autenticação GCP |
| `SERVICE_ACCOUNT_EMAIL` | Service account para GSC e outros |

### Renovar o OAuth token (se expirar)
1. Acessar [developers.google.com/oauthplayground](https://developers.google.com/oauthplayground)
2. Configurar com o Client ID e Secret do projeto `guanabara-seo`
3. Autorizar `https://www.googleapis.com/auth/analytics.readonly`
4. Trocar o código pelo token e atualizar o secret `GA4_OAUTH_REFRESH_TOKEN`

---

## Design System

Desenvolvido sobre o **Guanabara Design System v1.0**.

- **Fonte:** Nunito Sans (200–900)
- **Primário:** `#19398A` — azul corporativo
- **Secundário:** `#A43C3E` — vermelho Guanabara
- **Modo:** Dark mode adaptado do DS

---

## Stack técnica

| Camada | Tecnologia |
|---|---|
| Frontend | HTML · CSS · JavaScript (vanilla) · Chart.js 4 |
| Backend | Python 3.11 |
| CI/CD | GitHub Actions |
| Hospedagem | GitHub Pages |
| Auth GCP | Workload Identity Federation |
| Auth GA4 | OAuth 2.0 (refresh token) |

---

*SEO Command Center · Grupo Guanabara · Arara Tech · v2.0*
