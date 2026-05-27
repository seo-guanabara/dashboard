#!/usr/bin/env python3
"""
SEO Dashboard — Data Fetcher
Grupo Guanabara · viajeguanabara.com.br
Roda via GitHub Actions a cada 6h e grava data.json no repositório.
"""

import json, os, sys, traceback, time
from datetime import datetime, timedelta, date
import requests

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GA4_PROPERTY_ID = "152511726"
GSC_SITE_URL    = "https://viajeguanabara.com.br/"
YT_CHANNEL_ID   = "UCIIMGI6nclV5oKLruatE7QQ"
PLAY_PACKAGE    = "com.xvision.grupoguanabara"
SEMRUSH_DOMAIN  = "viajeguanabara.com.br"
COMPETITORS     = ["clickbus.com.br", "queropassagem.com.br"]
PERIOD_DAYS     = 30

today       = date.today()
p_end       = (today - timedelta(days=1)).isoformat()
p_start     = (today - timedelta(days=PERIOD_DAYS)).isoformat()
c_end       = (today - timedelta(days=PERIOD_DAYS + 1)).isoformat()
c_start     = (today - timedelta(days=PERIOD_DAYS * 2)).isoformat()

# ─── CREDENTIALS ──────────────────────────────────────────────────────────────
# Workload Identity Federation — credenciais injetadas pelo GitHub Actions
SEMRUSH_KEY  = os.environ.get("SEMRUSH_API_KEY", "")
GTMETRIX_KEY = os.environ.get("GTMETRIX_API_KEY", "")

SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/androidpublisher",
]

import google.auth
from google.auth.transport.requests import Request
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Metric, Dimension
from googleapiclient.discovery import build
import requests

creds, _ = google.auth.default(scopes=SCOPES)
creds.refresh(Request())

output = {
    "meta": {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "period_current":    {"start": p_start, "end": p_end},
        "period_comparison": {"start": c_start, "end": c_end},
    },
    "ga4":     {},
    "gsc":     {},
    "youtube": {},
    "play":    {},
    "semrush": {},
    "gtmetrix": {},
    "errors":  [],
}

def pct_delta(cur, prv):
    if not prv: return 0.0
    return round((cur - prv) / prv * 100, 1)

def log_ok(src):  print(f"  ✓ {src}")
def log_err(src, e):
    msg = f"{src}: {e}"
    output["errors"].append(msg)
    print(f"  ✗ {msg}")

# ─── GA4 VIA CSV ──────────────────────────────────────────────────────────────

# Fontes LLM reconhecidas
LLM_SOURCES = {
    "chatgpt.com / referral", "chatgpt.com / (not set)", "chatgpt.com / (none)",
    "gemini.google.com / referral",
    "copilot.microsoft.com / referral", "copilot.com / referral", "copilot.com / (not set)",
    "perplexity / (not set)",
    "claude.ai / referral",
    "l.meta.ai / referral",
}

def _read_ga4_csv(filepath):
    import csv as csv_module
    with open(filepath, encoding="utf-8-sig") as f:
        raw = f.read().replace("\r\n", "\n").replace("\r", "\n")
    lines = [l for l in raw.split("\n") if l.strip() and not l.startswith("#")]
    reader = csv_module.DictReader(lines)
    rows = list(reader)
    period_start = period_end = ""
    for line in raw.split("\n"):
        if "Data de início:" in line:
            d = line.split(":")[-1].strip()
            period_start = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d
        if "Data de término:" in line:
            d = line.split(":")[-1].strip()
            period_end = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d
    return rows, period_start, period_end

def _n(v):
    try: return float(str(v).replace(",", ".").strip())
    except: return 0.0

def parse_ga4_csvs(folder="ga4"):
    """
    Lê 3 CSVs do GA4:
      ga4/seo_traffic.csv    — tráfego filtrado por origens SEO (com transações)
      ga4/all_channels.csv   — todos os canais com transações (share de canal)
      ga4/transactions.csv   — transações por ID e origem/mídia
    """

    # ── 1. Tráfego SEO (origens SEO filtradas) ──
    seo_rows, p_start, p_end = _read_ga4_csv(f"{folder}/seo_traffic.csv")

    src_col = "Origem / mídia da sessão"
    seo_total = {"sessions":0,"new_users":0,"returning":0,"transactions":0,"revenue":0.0}
    seo_llm   = {"sessions":0,"new_users":0,"returning":0,"transactions":0,"revenue":0.0}
    seo_by_source = []

    for row in seo_rows:
        src  = row.get(src_col, "").strip()
        s    = int(_n(row.get("Sessões", 0)))
        nu   = int(_n(row.get("Novos usuários", 0)))
        ret  = int(_n(row.get("Usuários recorrentes", 0)))
        tx   = int(_n(row.get("Transações", 0)))
        rev  = round(_n(row.get("Receita total", 0)), 2)
        eng  = round(_n(row.get("Taxa de engajamento", 0)) * 100, 1)

        seo_total["sessions"]     += s
        seo_total["new_users"]    += nu
        seo_total["returning"]    += ret
        seo_total["transactions"] += tx
        seo_total["revenue"]      += rev

        is_llm = src in LLM_SOURCES
        if is_llm:
            seo_llm["sessions"]     += s
            seo_llm["new_users"]    += nu
            seo_llm["returning"]    += ret
            seo_llm["transactions"] += tx
            seo_llm["revenue"]      += rev

        seo_by_source.append({
            "source": src, "sessions": s, "new_users": nu,
            "returning": ret, "transactions": tx,
            "revenue": rev, "engagement": eng,
            "is_llm": is_llm,
        })

    # Ordenar por receita desc
    seo_by_source.sort(key=lambda x: x["revenue"], reverse=True)

    # Orgânico tradicional (SEO - LLM)
    seo_organic = {
        "sessions":     seo_total["sessions"]     - seo_llm["sessions"],
        "new_users":    seo_total["new_users"]     - seo_llm["new_users"],
        "returning":    seo_total["returning"]     - seo_llm["returning"],
        "transactions": seo_total["transactions"]  - seo_llm["transactions"],
        "revenue":      round(seo_total["revenue"] - seo_llm["revenue"], 2),
    }

    # ── 2. Todos os canais (share) ──
    all_rows, _, _ = _read_ga4_csv(f"{folder}/all_channels.csv")
    ch_col = "Grupo principal de canais da sessão (Grupo de Canais)"

    total_all = {"sessions":0,"transactions":0,"revenue":0.0}
    channels  = []
    for row in all_rows:
        s   = int(_n(row.get("Sessões", 0)))
        tx  = int(_n(row.get("Transações", 0)))
        rev = round(_n(row.get("Receita total", 0)), 2)
        total_all["sessions"]     += s
        total_all["transactions"] += tx
        total_all["revenue"]      += rev
        channels.append({
            "channel":      row.get(ch_col, "").strip(),
            "sessions":     s,
            "new_users":    int(_n(row.get("Novos usuários", 0))),
            "returning":    int(_n(row.get("Usuários recorrentes", 0))),
            "transactions": tx,
            "revenue":      rev,
        })
    channels.sort(key=lambda x: x["revenue"], reverse=True)

    # Share do SEO total
    def share(val, total):
        return round(val / total * 100, 1) if total else 0.0

    seo_share = {
        "sessions_pct":     share(seo_total["sessions"],     total_all["sessions"]),
        "transactions_pct": share(seo_total["transactions"], total_all["transactions"]),
        "revenue_pct":      share(seo_total["revenue"],      total_all["revenue"]),
    }
    llm_share = {
        "sessions_pct":     share(seo_llm["sessions"],     total_all["sessions"]),
        "transactions_pct": share(seo_llm["transactions"], total_all["transactions"]),
        "revenue_pct":      share(seo_llm["revenue"],      total_all["revenue"]),
    }

    # ── 3. Transações por origem ──
    tx_rows, _, _ = _read_ga4_csv(f"{folder}/transactions.csv")
    top_tx_sources = []
    for row in tx_rows[:20]:
        src = row.get("Origem / mídia da sessão", "").strip()
        purchases = int(_n(row.get("Compras de e-commerce", 0)))
        rev       = round(_n(row.get("Receita de compra", 0)), 2)
        if purchases > 0:
            top_tx_sources.append({
                "source":    src,
                "purchases": purchases,
                "revenue":   rev,
                "is_seo":    any(org in src for org in ["organic","chatgpt","gemini","copilot","perplexity","claude","meta.ai","duckduckgo","ecosia","yahoo","yandex"]),
            })

    return {
        "source":          "csv",
        "period_start":    p_start,
        "period_end":      p_end,
        # KPIs SEO (principais)
        "sessions":        seo_total["sessions"],
        "sessions_delta":  0.0,
        "new_users":       seo_total["new_users"],
        "new_users_delta": 0.0,
        "returning_users": seo_total["returning"],
        "returning_delta": 0.0,
        "transactions":    seo_total["transactions"],
        "transactions_delta": 0.0,
        "revenue":         round(seo_total["revenue"], 2),
        "revenue_delta":   0.0,
        "daily_sessions":  [],
        # Detalhes
        "seo_total":       seo_total,
        "seo_organic":     seo_organic,
        "seo_llm":         seo_llm,
        "seo_by_source":   seo_by_source,
        "seo_share":       seo_share,
        "llm_share":       llm_share,
        "channels":        channels,
        "total_all":       total_all,
        "top_tx_sources":  top_tx_sources,
    }

# ─── GA4 ──────────────────────────────────────────────────────────────────────
def fetch_ga4():
    # Tenta pasta ga4/ com os 3 CSVs segmentados
    if os.path.exists("ga4/seo_traffic.csv"):
        try:
            output["ga4"] = parse_ga4_csvs("ga4")
            log_ok("GA4 (CSV segmentado — SEO/LLM/canais)")
            return
        except Exception as e:
            log_err("GA4 CSV parse", str(e))
    # Fallback: CSV único de aquisição geral
    if os.path.exists("ga4_export.csv"):
        try:
            output["ga4"] = parse_ga4_csvs_legacy("ga4_export.csv")
            log_ok("GA4 (CSV legado)")
            return
        except Exception as e:
            log_err("GA4 CSV legado", str(e))

    try:
        client = BetaAnalyticsDataClient(credentials=creds)

        def report(metrics, dimensions=None, date_ranges=None, limit=100):
            return client.run_report(RunReportRequest(
                property=f"properties/{GA4_PROPERTY_ID}",
                metrics=[Metric(name=m) for m in metrics],
                dimensions=[Dimension(name=d) for d in (dimensions or [])],
                date_ranges=date_ranges or [
                    DateRange(start_date=p_start, end_date=p_end),
                    DateRange(start_date=c_start, end_date=c_end),
                ],
                limit=limit,
            ))

        def fv(rows, row_i, metric_i):
            try: return float(rows[row_i].metric_values[metric_i].value)
            except: return 0.0

        # KPIs — duas datas ao mesmo tempo (current = date_range_0, prev = date_range_1)
        r = report(["sessions", "newUsers", "transactions", "purchaseRevenue"])
        rows = r.rows

        # GA4 retorna linhas agrupadas por dateRange quando sem dimensão
        cur = {row.dimension_values[0].value: row for row in rows if row.dimension_values[0].value == "date_range_0"}
        prv = {row.dimension_values[0].value: row for row in rows if row.dimension_values[0].value == "date_range_1"}

        def mv(d, mi):
            row = list(d.values())[0] if d else None
            return float(row.metric_values[mi].value) if row else 0.0

        sessions     = int(mv(cur, 0))
        new_users    = int(mv(cur, 1))
        transactions = int(mv(cur, 2))
        revenue      = round(mv(cur, 3), 2)
        p_sessions   = int(mv(prv, 0))
        p_new_users  = int(mv(prv, 1))
        p_trans      = int(mv(prv, 2))
        p_revenue    = round(mv(prv, 3), 2)

        # Returning users
        r2 = client.run_report(RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            metrics=[Metric(name="sessions")],
            dimensions=[Dimension(name="newVsReturning"), Dimension(name="dateRange")],
            date_ranges=[
                DateRange(start_date=p_start, end_date=p_end),
                DateRange(start_date=c_start, end_date=c_end),
            ],
            limit=10,
        ))
        returning_cur = returning_prv = 0
        for row in r2.rows:
            nv = row.dimension_values[0].value
            dr = row.dimension_values[1].value
            val = int(row.metric_values[0].value)
            if nv == "returning" and dr == "date_range_0": returning_cur = val
            if nv == "returning" and dr == "date_range_1": returning_prv = val

        # Daily sessions para sparkline
        r3 = client.run_report(RunReportRequest(
            property=f"properties/{GA4_PROPERTY_ID}",
            metrics=[Metric(name="sessions")],
            dimensions=[Dimension(name="date")],
            date_ranges=[DateRange(start_date=p_start, end_date=p_end)],
            limit=31,
        ))
        daily = [int(row.metric_values[0].value)
                 for row in sorted(r3.rows, key=lambda x: x.dimension_values[0].value)]

        output["ga4"] = {
            "sessions":            sessions,
            "sessions_delta":      pct_delta(sessions, p_sessions),
            "new_users":           new_users,
            "new_users_delta":     pct_delta(new_users, p_new_users),
            "returning_users":     returning_cur,
            "returning_delta":     pct_delta(returning_cur, returning_prv),
            "transactions":        transactions,
            "transactions_delta":  pct_delta(transactions, p_trans),
            "revenue":             revenue,
            "revenue_delta":       pct_delta(revenue, p_revenue),
            "daily_sessions":      daily,
        }
        log_ok("GA4")
    except Exception as e:
        log_err("GA4", traceback.format_exc())

# ─── GSC VIA CSV ──────────────────────────────────────────────────────────────
def parse_gsc_csvs(folder="gsc"):
    """
    Lê CSVs exportados do GSC (Desempenho → Exportar CSV).
    Arquivos esperados na pasta gsc/:
      - Gráfico.csv   → dados diários (Data, Cliques, Impressões, CTR, Posição)
      - Consultas.csv → top queries agregadas
      - Páginas.csv   → top páginas agregadas
    Detecta automaticamente o range de datas e calcula períodos de comparação.
    """
    import csv as csv_module

    def num(v):
        try: return float(str(v).replace("%","").replace(",",".").strip())
        except: return 0.0

    # ── Gráfico.csv — dados diários ──
    with open(f"{folder}/Gráfico.csv", encoding="utf-8") as f:
        daily_rows = list(csv_module.DictReader(f))
    daily_rows.sort(key=lambda x: x["Data"])

    last_date  = datetime.strptime(daily_rows[-1]["Data"], "%Y-%m-%d").date()
    cur_end    = last_date
    cur_start  = cur_end  - timedelta(days=29)
    prev_end   = cur_start - timedelta(days=1)
    prev_start = prev_end  - timedelta(days=29)

    cur_rows  = [r for r in daily_rows if cur_start.isoformat()  <= r["Data"] <= cur_end.isoformat()]
    prev_rows = [r for r in daily_rows if prev_start.isoformat() <= r["Data"] <= prev_end.isoformat()]

    def period_stats(rows):
        if not rows: return {"clicks":0,"impressions":0,"ctr":0.0,"position":0.0}
        clicks      = sum(int(r["Cliques"]) for r in rows)
        impressions = sum(int(r["Impressões"]) for r in rows)
        ctr         = round(sum(num(r["CTR"]) for r in rows) / len(rows), 2)
        position    = round(sum(num(r["Posição"]) for r in rows) / len(rows), 1)
        return {"clicks": clicks, "impressions": impressions, "ctr": ctr, "position": position}

    cs = period_stats(cur_rows)
    ps = period_stats(prev_rows)

    # ── Consultas.csv — top queries ──
    with open(f"{folder}/Consultas.csv", encoding="utf-8") as f:
        query_rows = list(csv_module.DictReader(f))

    top_queries = []
    for row in query_rows[:20]:
        top_queries.append({
            "query":       row["Top consultas"],
            "clicks":      int(row["Cliques"]),
            "impressions": int(row["Impressões"]),
            "ctr":         round(num(row["CTR"]), 2),
            "position":    round(num(row["Posição"]), 1),
            "pos_delta":   0.0,
        })

    # ── Páginas.csv — páginas em queda (compara 1ª vs 2ª metade do período) ──
    with open(f"{folder}/Páginas.csv", encoding="utf-8") as f:
        page_rows = list(csv_module.DictReader(f))

    # Usa dados diários para identificar páginas com queda
    # Como o CSV de páginas é agregado, usamos ranking de cliques como proxy
    declining = []
    for row in page_rows:
        path = row["Páginas principais"].replace(GSC_SITE_URL.rstrip("/"), "") or "/"
        clicks = int(row["Cliques"])
        if clicks < 500:  # foca em páginas com volume relevante
            continue
        declining.append({"page": path, "clicks": clicks, "delta": 0.0})
    # Ordena por menor CTR como indicador de oportunidade
    page_rows_sorted = sorted(page_rows, key=lambda x: num(x["CTR"]))
    declining = []
    for row in page_rows_sorted[:5]:
        path = row["Páginas principais"].replace(GSC_SITE_URL.rstrip("/"), "") or "/"
        declining.append({
            "page":   path,
            "clicks": int(row["Cliques"]),
            "delta":  round(num(row["CTR"]) - (cs["ctr"] or 1), 2),
        })

    # ── Coverage (indexação) ──
    indexed_pages     = 0
    indexed_daily     = []
    coverage_urls     = []
    if os.path.exists(f"{folder}/coverage/Gráfico.csv"):
        with open(f"{folder}/coverage/Gráfico.csv", encoding="utf-8") as f:
            cov_rows = list(csv_module.DictReader(f))
        if cov_rows:
            indexed_pages = int(num(cov_rows[-1].get("Páginas afetadas", 0)))
            indexed_daily = [int(num(r.get("Páginas afetadas", 0))) for r in cov_rows[-30:]]
    if os.path.exists(f"{folder}/coverage/Tabela.csv"):
        with open(f"{folder}/coverage/Tabela.csv", encoding="utf-8") as f:
            cov_table = list(csv_module.DictReader(f))
        coverage_urls = [{"url": r.get("URL",""), "last_crawl": r.get("Último rastreamento","")}
                         for r in cov_table[:20]]

    # ── Core Web Vitals ──
    cwv_issues    = []
    cwv_daily_bad = []
    cwv_daily_ok  = []
    if os.path.exists(f"{folder}/cwv/Tabela.csv"):
        with open(f"{folder}/cwv/Tabela.csv", encoding="utf-8") as f:
            cwv_rows = list(csv_module.DictReader(f))
        for row in cwv_rows:
            cwv_issues.append({
                "severity": row.get("Gravidade",""),
                "issue":    row.get("Problema",""),
                "urls":     int(num(row.get("URLs", 0))),
            })
    if os.path.exists(f"{folder}/cwv/Gráfico.csv"):
        with open(f"{folder}/cwv/Gráfico.csv", encoding="utf-8") as f:
            cwv_chart = list(csv_module.DictReader(f))
        cwv_daily_bad = [int(num(r.get("Ruins",0)))              for r in cwv_chart[-30:]]
        cwv_daily_ok  = [int(num(r.get("Bom",0)))                for r in cwv_chart[-30:]]

    # ── Backlinks ──
    backlinks_total = 0
    if os.path.exists(f"{folder}/Latest_links.csv"):
        with open(f"{folder}/Latest_links.csv", encoding="utf-8") as f:
            bl_rows = list(csv_module.DictReader(f))
        backlinks_total = len(bl_rows)

    return {
        "source":            "csv",
        "period_start":      cur_start.isoformat(),
        "period_end":        cur_end.isoformat(),
        "clicks":            cs["clicks"],
        "clicks_delta":      pct_delta(cs["clicks"],      ps["clicks"]),
        "impressions":       cs["impressions"],
        "impressions_delta": pct_delta(cs["impressions"], ps["impressions"]),
        "ctr":               cs["ctr"],
        "ctr_delta":         round(cs["ctr"] - ps["ctr"], 2),
        "position":          cs["position"],
        "position_delta":    round(ps["position"] - cs["position"], 1),
        "top_queries":       top_queries[:10],
        "declining_pages":   declining,
        "daily_clicks":      [int(r["Cliques"])     for r in cur_rows],
        "daily_clicks_prev": [int(r["Cliques"])     for r in prev_rows],
        "daily_impressions": [int(r["Impressões"])  for r in cur_rows],
        "all_daily": [
            {
                "date":        r["Data"],
                "clicks":      int(r["Cliques"]),
                "impressions": int(r["Impressões"]),
                "ctr":         round(num(r["CTR"]), 2),
                "position":    round(num(r["Posição"]), 1),
            }
            for r in daily_rows
        ],
        "data_start": daily_rows[0]["Data"],
        "data_end":   daily_rows[-1]["Data"],
        "indexed_pages":     indexed_pages,
        "indexed_daily":     indexed_daily,
        "coverage_urls":     coverage_urls,
        "cwv_issues":        cwv_issues,
        "cwv_daily_bad":     cwv_daily_bad,
        "cwv_daily_ok":      cwv_daily_ok,
        "backlinks_total":   backlinks_total,
    }

def fetch_gsc():
    # Tenta pasta gsc/ com CSVs exportados, depois API
    if os.path.exists("gsc/Gráfico.csv"):
        try:
            output["gsc"] = parse_gsc_csvs("gsc")
            log_ok("GSC (CSV)")
            return
        except Exception as e:
            log_err("GSC CSV parse", str(e))

    # Fallback API (requer permissão na propriedade)
    try:
        svc = build("searchconsole", "v1", credentials=creds)
        sc  = svc.searchanalytics()

        def query(start, end, dims=None, limit=25):
            body = {"startDate": start, "endDate": end,
                    "dimensions": dims or [], "rowLimit": limit}
            return sc.query(siteUrl=GSC_SITE_URL, body=body).execute()

        rc = query(p_start, p_end)
        rp = query(c_start, c_end)

        def kpi(r, k):
            return r.get("rows", [{}])[0].get(k, 0) if r.get("rows") else 0

        clicks_c  = int(kpi(rc, "clicks"));  clicks_p  = int(kpi(rp, "clicks"))
        impr_c    = int(kpi(rc, "impressions")); impr_p = int(kpi(rp, "impressions"))
        ctr_c     = round(kpi(rc, "ctr") * 100, 2); ctr_p = round(kpi(rp, "ctr") * 100, 2)
        pos_c     = round(kpi(rc, "position"), 1); pos_p = round(kpi(rp, "position"), 1)

        tq_c = query(p_start, p_end, ["query"], 20)
        tq_p = query(c_start, c_end, ["query"], 20)
        prev_q = {r["keys"][0]: r for r in tq_p.get("rows", [])}
        top_queries = []
        for row in tq_c.get("rows", []):
            q  = row["keys"][0]
            pv = prev_q.get(q, {})
            top_queries.append({"query": q, "clicks": row.get("clicks",0),
                "impressions": row.get("impressions",0),
                "ctr": round(row.get("ctr",0)*100,2),
                "position": round(row.get("position",99),1),
                "pos_delta": round(pv.get("position", row["position"]) - row["position"], 1)})

        dq_c = query(p_start, p_end, ["date"], 31)
        dq_p = query(c_start, c_end, ["date"], 31)
        dc   = sorted(dq_c.get("rows",[]), key=lambda x: x["keys"][0])
        dp   = sorted(dq_p.get("rows",[]), key=lambda x: x["keys"][0])

        output["gsc"] = {
            "clicks": clicks_c, "clicks_delta": pct_delta(clicks_c, clicks_p),
            "impressions": impr_c, "impressions_delta": pct_delta(impr_c, impr_p),
            "ctr": ctr_c, "ctr_delta": round(ctr_c - ctr_p, 2),
            "position": pos_c, "position_delta": round(pos_p - pos_c, 1),
            "top_queries": top_queries[:10], "declining_pages": [],
            "daily_clicks": [r["clicks"] for r in dc],
            "daily_clicks_prev": [r["clicks"] for r in dp],
            "daily_impressions": [r["impressions"] for r in dc],
        }
        log_ok("GSC (API)")
    except Exception as e:
        log_err("GSC", traceback.format_exc())

# ─── YOUTUBE ANALYTICS ────────────────────────────────────────────────────────
def fetch_youtube():
    # Requer canal linkado ao GA4 — habilitado quando vinculação estiver feita
    output["youtube"] = {"views": 0, "views_delta": 0, "watch_time": 0,
                         "subs_gained": 0, "subs_lost": 0, "impressions": 0, "ctr": 0.0,
                         "status": "pending_channel_link"}
    log_ok("YouTube (pendente vinculação do canal)")

# ─── GOOGLE PLAY ──────────────────────────────────────────────────────────────
def fetch_play():
    # Stand by — aguardando permissão no Play Console
    output["play"] = {"status": "pending_permission"}
    log_ok("Play Console (stand by)")

# ─── SEMRUSH ──────────────────────────────────────────────────────────────────
def fetch_semrush():
    if not SEMRUSH_KEY:
        output["semrush"] = {"error": "SEMRUSH_API_KEY not set"}
        return
    try:
        base = "https://api.semrush.com/"

        def sem(params):
            params["key"] = SEMRUSH_KEY
            r = requests.get(base, params=params, timeout=20)
            r.raise_for_status()
            return r.text

        # Posições orgânicas do domínio
        kw_raw = sem({
            "type": "domain_organic",
            "domain": SEMRUSH_DOMAIN,
            "database": "br",
            "display_limit": 10000,
            "export_columns": "Ph,Po,Nq,Tr,Fk",
        })
        lines = [l.split(";") for l in kw_raw.strip().split("\n")[1:] if l]

        top1 = top3 = top10 = top20 = 0
        serp_ai = serp_fsnippet = serp_paa = serp_sitelinks = 0
        for parts in lines:
            if len(parts) < 5: continue
            try:
                pos   = int(parts[1])
                feats = parts[4] if len(parts) > 4 else ""
                if pos == 1:  top1  += 1
                if pos <= 3:  top3  += 1
                if pos <= 10: top10 += 1
                if pos <= 20: top20 += 1
                if "28" in feats: serp_ai       += 1  # AI Overview feature code
                if "2"  in feats: serp_fsnippet += 1
                if "8"  in feats: serp_paa      += 1
                if "4"  in feats: serp_sitelinks += 1
            except: pass

        total = len(lines)

        # Competidores
        comp_data = {}
        for comp in COMPETITORS:
            time.sleep(0.5)  # respeitar rate limit
            raw = sem({"type": "domain_organic", "domain": comp, "database": "br",
                       "display_limit": 1, "export_columns": "Or,Ot"})
            cl = [l.split(";") for l in raw.strip().split("\n") if l]
            kws = traffic = 0
            if len(cl) > 1 and len(cl[1]) >= 2:
                try: kws     = int(cl[1][0] or 0)
                except: pass
                try: traffic = int(cl[1][1] or 0)
                except: pass
            comp_data[comp] = {"keywords": kws, "traffic": traffic}

        # Domínio próprio overview
        my_raw = sem({"type": "domain_organic", "domain": SEMRUSH_DOMAIN, "database": "br",
                      "display_limit": 1, "export_columns": "Or,Ot"})
        my_cl = [l.split(";") for l in my_raw.strip().split("\n") if l]
        my_traffic = 0
        if len(my_cl) > 1 and len(my_cl[1]) >= 2:
            try: my_traffic = int(my_cl[1][1] or 0)
            except: pass

        comp_data[SEMRUSH_DOMAIN] = {"keywords": total, "traffic": my_traffic}

        output["semrush"] = {
            "total_keywords": total,
            "top1":  top1,
            "top3":  top3,
            "top10": top10,
            "top20": top20,
            "rank_distribution": [top1, top3 - top1, top10 - top3, top20 - top10, total - top20],
            "serp_features": {
                "ai_overview":      serp_ai,
                "featured_snippet": serp_fsnippet,
                "people_also_ask":  serp_paa,
                "sitelinks":        serp_sitelinks,
            },
            "competitors": comp_data,
        }
        log_ok("Semrush")
    except Exception as e:
        log_err("Semrush", traceback.format_exc())

# ─── GTMETRIX ─────────────────────────────────────────────────────────────────
def fetch_gtmetrix():
    if not GTMETRIX_KEY:
        output["gtmetrix"] = {"error": "GTMETRIX_API_KEY not set"}
        return
    try:
        pages = [
            {"url": f"{GSC_SITE_URL}",                 "layout": "home"},
            {"url": f"{GSC_SITE_URL}passagem-onibus",  "layout": "listagem"},
        ]
        results = []
        for p in pages:
            r = requests.post(
                "https://gtmetrix.com/api/2.0/tests",
                auth=(GTMETRIX_KEY, ""),
                json={"data": {"type": "test", "attributes": {"url": p["url"]}}},
                timeout=15,
            )
            if r.status_code == 202:
                test_id = r.json()["data"]["id"]
                # Poll result (max 60s)
                for _ in range(12):
                    time.sleep(5)
                    tr = requests.get(
                        f"https://gtmetrix.com/api/2.0/tests/{test_id}",
                        auth=(GTMETRIX_KEY, ""),
                        timeout=15,
                    ).json()
                    state = tr["data"]["attributes"].get("state")
                    if state == "completed":
                        attrs = tr["data"]["attributes"]
                        results.append({
                            "layout":      p["layout"],
                            "url":         p["url"],
                            "score":       attrs.get("gtmetrix_grade"),
                            "performance": round(attrs.get("performance_score", 0) * 100),
                            "lcp":         attrs.get("largest_contentful_paint"),
                            "cls":         attrs.get("cumulative_layout_shift"),
                            "inp":         attrs.get("interaction_to_next_paint"),
                        })
                        break
                    elif state == "error":
                        break

        output["gtmetrix"] = {"pages": results}
        log_ok("GTmetrix")
    except Exception as e:
        log_err("GTmetrix", traceback.format_exc())

# ─── EXECUTAR TUDO ────────────────────────────────────────────────────────────
print("\n── Buscando dados ──────────────────────────────")
fetch_ga4()
fetch_gsc()
fetch_youtube()
fetch_play()
fetch_semrush()
fetch_gtmetrix()

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n── Concluído ───────────────────────────────────")
print(f"   data.json salvo · erros: {len(output['errors'])}")
for err in output["errors"]:
    print(f"   • {err[:120]}")

# Só falha se GA4 e GSC tiverem erros simultaneamente (ambos são críticos)
critical_errors = [e for e in output["errors"] if e.startswith(("GA4", "GSC"))]
sys.exit(1 if critical_errors else 0)
