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

# ─── GA4 ──────────────────────────────────────────────────────────────────────
def fetch_ga4():
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

# ─── GSC ──────────────────────────────────────────────────────────────────────
def fetch_gsc():
    try:
        svc = build("searchconsole", "v1", credentials=creds)
        sc  = svc.searchanalytics()

        def query(start, end, dims=None, limit=25):
            body = {"startDate": start, "endDate": end,
                    "dimensions": dims or [], "rowLimit": limit}
            return sc.query(siteUrl=GSC_SITE_URL, body=body).execute()

        # Overview
        rc = query(p_start, p_end)
        rp = query(c_start, c_end)

        def kpi(r, k):
            return r.get("rows", [{}])[0].get(k, 0) if r.get("rows") else 0

        clicks_c      = int(kpi(rc, "clicks"))
        impr_c        = int(kpi(rc, "impressions"))
        ctr_c         = round(kpi(rc, "ctr") * 100, 2)
        pos_c         = round(kpi(rc, "position"), 1)
        clicks_p      = int(kpi(rp, "clicks"))
        impr_p        = int(kpi(rp, "impressions"))
        ctr_p         = round(kpi(rp, "ctr") * 100, 2)
        pos_p         = round(kpi(rp, "position"), 1)

        # Top queries com delta
        tq_c = query(p_start, p_end, ["query"], 20)
        tq_p = query(c_start, c_end, ["query"], 20)
        prev_q = {r["keys"][0]: r for r in tq_p.get("rows", [])}
        top_queries = []
        for row in tq_c.get("rows", []):
            q = row["keys"][0]
            pv = prev_q.get(q, {})
            top_queries.append({
                "query":       q,
                "clicks":      row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr":         round(row.get("ctr", 0) * 100, 2),
                "position":    round(row.get("position", 99), 1),
                "pos_delta":   round(pv.get("position", row["position"]) - row["position"], 1),
            })

        # Páginas em queda
        tp_c = query(p_start, p_end, ["page"], 25)
        tp_p = query(c_start, c_end, ["page"], 25)
        prev_pg = {r["keys"][0]: r for r in tp_p.get("rows", [])}
        declining = []
        for row in tp_c.get("rows", []):
            pg = row["keys"][0]
            pv = prev_pg.get(pg)
            if pv:
                d = pct_delta(row["clicks"], pv["clicks"])
                if d < -10:
                    path = pg.replace(GSC_SITE_URL.rstrip("/"), "") or "/"
                    declining.append({"page": path, "clicks": row["clicks"], "delta": d})
        declining.sort(key=lambda x: x["delta"])

        # Daily
        dq_c = query(p_start, p_end, ["date"], 31)
        dq_p = query(c_start, c_end, ["date"], 31)
        dc = sorted(dq_c.get("rows", []), key=lambda x: x["keys"][0])
        dp = sorted(dq_p.get("rows", []), key=lambda x: x["keys"][0])

        output["gsc"] = {
            "clicks":            clicks_c,
            "clicks_delta":      pct_delta(clicks_c, clicks_p),
            "impressions":       impr_c,
            "impressions_delta": pct_delta(impr_c, impr_p),
            "ctr":               ctr_c,
            "ctr_delta":         round(ctr_c - ctr_p, 2),
            "position":          pos_c,
            "position_delta":    round(pos_p - pos_c, 1),
            "top_queries":       top_queries[:10],
            "declining_pages":   declining[:5],
            "daily_clicks":      [r["clicks"] for r in dc],
            "daily_clicks_prev": [r["clicks"] for r in dp],
            "daily_impressions": [r["impressions"] for r in dc],
        }
        log_ok("GSC")
    except Exception as e:
        log_err("GSC", traceback.format_exc())

# ─── YOUTUBE ANALYTICS ────────────────────────────────────────────────────────
def fetch_youtube():
    try:
        yt = build("youtubeAnalytics", "v2", credentials=creds)
        r  = yt.reports().query(
            ids=f"channel=={YT_CHANNEL_ID}",
            startDate=p_start, endDate=p_end,
            metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost,impressions,impressionClickThroughRate",
        ).execute()
        rp = yt.reports().query(
            ids=f"channel=={YT_CHANNEL_ID}",
            startDate=c_start, endDate=c_end,
            metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost,impressions,impressionClickThroughRate",
        ).execute()

        row  = r.get("rows",  [[0]*6])[0]
        rowp = rp.get("rows", [[0]*6])[0]

        output["youtube"] = {
            "views":          int(row[0]),
            "views_delta":    pct_delta(int(row[0]), int(rowp[0])),
            "watch_time":     int(row[1]),
            "subs_gained":    int(row[2]),
            "subs_lost":      int(row[3]),
            "impressions":    int(row[4]),
            "ctr":            round(float(row[5]) * 100, 2),
        }
        log_ok("YouTube")
    except Exception as e:
        log_err("YouTube", traceback.format_exc())

# ─── GOOGLE PLAY ──────────────────────────────────────────────────────────────
def fetch_play():
    try:
        svc = build("androidpublisher", "v3", credentials=creds)
        rev = svc.reviews().list(packageName=PLAY_PACKAGE, maxResults=1).execute()
        output["play"] = {
            "total_reviews": rev.get("tokenPagination", {}).get("nextPageToken", "n/a"),
            "note": "installs via Google Play Developer Reporting API (separate quota)",
        }
        log_ok("Play Console (reviews)")
    except Exception as e:
        log_err("Play Console", traceback.format_exc())

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

sys.exit(1 if output["errors"] else 0)
