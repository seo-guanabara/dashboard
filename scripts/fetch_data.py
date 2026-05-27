#!/usr/bin/env python3
"""
SEO Dashboard — Data Fetcher v2
Grupo Guanabara · viajeguanabara.com.br
"""

import json, os, sys, traceback, time, csv as csv_module
from datetime import datetime, timedelta, date
import requests

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GA4_PROPERTY_ID       = "152511726"
GA4_BLOG_PROPERTY_ID  = "359547158"
GA4_VIVA_PROPERTY_ID  = "202055102"
GSC_SITE_URL          = "https://viajeguanabara.com.br/"
GSC_BLOG_URL          = "https://blog.viajeguanabara.com.br/"
GSC_VIVA_URL          = "https://www.vivafidelidade.com.br/"
# Propriedades extras — todos em gsc/grafico_*.csv
GSC_EXTRA_FILES = {
    "gsc/grafico_novo.csv":     "novo.viajeguanabara.com.br",
    "gsc/grafico_www.csv":      "www.viajeguanabara.com.br",
    "gsc/grafico_mkt.csv":      "mkt.viajeguanabara.com.br",
    "gsc/grafico_destinos.csv": "destinos.viajeguanabara.com.br",
    "gsc/grafico_blog.csv":     "blog.viajeguanabara.com.br",
}
YT_CHANNEL_ID         = "UCIIMGI6nclV5oKLruatE7QQ"
PLAY_PACKAGE    = "com.xvision.grupoguanabara"
SEMRUSH_DOMAIN  = "viajeguanabara.com.br"
COMPETITORS     = ["clickbus.com.br", "queropassagem.com.br"]
PERIOD_DAYS     = 30

today   = date.today()
p_end   = (today - timedelta(days=1)).isoformat()
p_start = (today - timedelta(days=PERIOD_DAYS)).isoformat()
c_end   = (today - timedelta(days=PERIOD_DAYS + 1)).isoformat()
c_start = (today - timedelta(days=PERIOD_DAYS * 2)).isoformat()
ytd_start = date(today.year, 1, 1).isoformat()

LLM_SOURCES = {
    "chatgpt.com / referral","chatgpt.com / (not set)","chatgpt.com / (none)",
    "gemini.google.com / referral",
    "copilot.microsoft.com / referral","copilot.com / referral","copilot.com / (not set)",
    "perplexity / (not set)","claude.ai / referral","l.meta.ai / referral",
}

# ─── CREDENTIALS ──────────────────────────────────────────────────────────────
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
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Metric, Dimension, FilterExpression,
    Filter, FilterExpressionList
)
from googleapiclient.discovery import build

creds, _ = google.auth.default(scopes=SCOPES)
creds.refresh(Request())

output = {
    "meta": {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "period_current":    {"start": p_start, "end": p_end},
        "period_comparison": {"start": c_start, "end": c_end},
        "period_ytd":        {"start": ytd_start, "end": p_end},
    },
    "ga4": {}, "gsc": {}, "youtube": {}, "play": {},
    "semrush": {}, "gtmetrix": {}, "errors": [],
}

def pct(cur, prv):
    if not prv: return 0.0
    return round((cur - prv) / prv * 100, 1)

def log_ok(s):  print(f"  ✓ {s}")
def log_err(s, e):
    msg = f"{s}: {str(e)[:200]}"
    output["errors"].append(msg)
    print(f"  ✗ {msg}")

# ─── HELPERS CSV ──────────────────────────────────────────────────────────────
def read_ga4_csv(filepath):
    with open(filepath, encoding="utf-8-sig") as f:
        raw = f.read().replace("\r\n","\n").replace("\r","\n")
    lines = [l for l in raw.split("\n") if l.strip() and not l.startswith("#")]
    rows  = list(csv_module.DictReader(lines))
    p_start_csv = p_end_csv = ""
    for line in raw.split("\n"):
        if "Data de início:" in line:
            d = line.split(":")[-1].strip()
            p_start_csv = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d)==8 else d
        if "Data de término:" in line:
            d = line.split(":")[-1].strip()
            p_end_csv = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d)==8 else d
    return rows, p_start_csv, p_end_csv

def _n(v):
    try: return float(str(v).replace(",",".").strip())
    except: return 0.0

# ─── GA4 API ──────────────────────────────────────────────────────────────────
def fetch_ga4_api():
    client = BetaAnalyticsDataClient(credentials=creds)

    def rpt(metrics, dims=None, date_ranges=None, limit=100, dim_filter=None):
        kwargs = dict(
            property=f"properties/{GA4_PROPERTY_ID}",
            metrics=[Metric(name=m) for m in metrics],
            dimensions=[Dimension(name=d) for d in (dims or [])],
            date_ranges=date_ranges or [
                DateRange(start_date=p_start, end_date=p_end),
                DateRange(start_date=c_start, end_date=c_end),
            ],
            limit=limit,
        )
        if dim_filter: kwargs["dimension_filter"] = dim_filter
        return client.run_report(RunReportRequest(**kwargs))

    def mv(row, i):
        try: return float(row.metric_values[i].value)
        except: return 0.0

    # ── KPIs totais ──
    r = rpt(["sessions","newUsers","transactions","purchaseRevenue"])
    cur = {row.dimension_values[0].value: row for row in r.rows if row.dimension_values[0].value == "date_range_0"}
    prv = {row.dimension_values[0].value: row for row in r.rows if row.dimension_values[0].value == "date_range_1"}

    def gv(d, i):
        row = list(d.values())[0] if d else None
        return float(row.metric_values[i].value) if row else 0.0

    sessions   = int(gv(cur,0));  p_sessions   = int(gv(prv,0))
    new_users  = int(gv(cur,1));  p_new_users  = int(gv(prv,1))
    trans      = int(gv(cur,2));  p_trans      = int(gv(prv,2))
    revenue    = round(gv(cur,3),2); p_revenue = round(gv(prv,3),2)

    # ── YTD receita ──
    r_ytd = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        metrics=[Metric(name="purchaseRevenue")],
        date_ranges=[DateRange(start_date=ytd_start, end_date=p_end)],
        limit=1,
    ))
    revenue_ytd = round(float(r_ytd.rows[0].metric_values[0].value),2) if r_ytd.rows else 0.0

    # ── Returning users ──
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

    # ── Daily sessions ──
    r3 = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        metrics=[Metric(name="sessions")],
        dimensions=[Dimension(name="date")],
        date_ranges=[DateRange(start_date=p_start, end_date=p_end)],
        limit=31,
    ))
    daily = [int(row.metric_values[0].value)
             for row in sorted(r3.rows, key=lambda x: x.dimension_values[0].value)]

    # ── Channels para share ──
    r4 = rpt(["sessions","transactions","purchaseRevenue"],
             dims=["sessionDefaultChannelGroup"], limit=20)
    channels = []
    for row in r4.rows:
        dr = row.dimension_values[1].value if len(row.dimension_values) > 1 else "date_range_0"
        if dr != "date_range_0": continue
        channels.append({
            "channel":      row.dimension_values[0].value,
            "sessions":     int(mv(row,0)),
            "transactions": int(mv(row,1)),
            "revenue":      round(mv(row,2),2),
        })
    channels.sort(key=lambda x: x["revenue"], reverse=True)
    total_all = {
        "sessions":     sum(c["sessions"]     for c in channels),
        "transactions": sum(c["transactions"] for c in channels),
        "revenue":      sum(c["revenue"]      for c in channels),
    }

    # ── Top páginas de rotas ──
    r5 = client.run_report(RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        metrics=[Metric(name="sessions"),Metric(name="purchaseRevenue")],
        dimensions=[Dimension(name="pagePath")],
        date_ranges=[DateRange(start_date=p_start, end_date=p_end)],
        dimension_filter=FilterExpression(
            filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.BEGINS_WITH,
                    value="/onibus/"
                )
            )
        ),
        limit=20,
        order_bys=[],
    ))
    top_routes = sorted([{
        "path":     row.dimension_values[0].value,
        "sessions": int(mv(row,0)),
        "revenue":  round(mv(row,1),2),
    } for row in r5.rows], key=lambda x: x["sessions"], reverse=True)[:10]

    output["ga4"] = {
        "source":            "api",
        "period_start":      p_start,
        "period_end":        p_end,
        "sessions":          sessions,
        "sessions_delta":    pct(sessions, p_sessions),
        "new_users":         new_users,
        "new_users_delta":   pct(new_users, p_new_users),
        "returning_users":   returning_cur,
        "returning_delta":   pct(returning_cur, returning_prv),
        "transactions":      trans,
        "transactions_delta":pct(trans, p_trans),
        "revenue":           revenue,
        "revenue_delta":     pct(revenue, p_revenue),
        "revenue_ytd":       revenue_ytd,
        "daily_sessions":    daily,
        "channels":          channels,
        "total_all":         total_all,
        "top_routes":        top_routes,
        "conv_rate":         round(trans/sessions*100, 2) if sessions else 0,
    }

# ─── GA4 CSV FALLBACK ─────────────────────────────────────────────────────────
def fetch_ga4_csv():
    folder = "ga4"
    rows, p_s, p_e = read_ga4_csv(f"{folder}/seo_traffic.csv")
    src_col = "Origem / mídia da sessão"
    seo_total = {"sessions":0,"new_users":0,"returning":0,"transactions":0,"revenue":0.0}
    seo_llm   = {"sessions":0,"new_users":0,"returning":0,"transactions":0,"revenue":0.0}
    seo_by_source = []
    for row in rows:
        src = row.get(src_col,"").strip()
        s   = int(_n(row.get("Sessões",0)))
        nu  = int(_n(row.get("Novos usuários",0)))
        ret = int(_n(row.get("Usuários recorrentes",0)))
        tx  = int(_n(row.get("Transações",0)))
        rev = round(_n(row.get("Receita total",0)),2)
        for k,v in [("sessions",s),("new_users",nu),("returning",ret),("transactions",tx)]:
            seo_total[k] += v
        seo_total["revenue"] += rev
        is_llm = src in LLM_SOURCES
        if is_llm:
            for k,v in [("sessions",s),("new_users",nu),("returning",ret),("transactions",tx)]:
                seo_llm[k] += v
            seo_llm["revenue"] += rev
        seo_by_source.append({"source":src,"sessions":s,"new_users":nu,"returning":ret,
                               "transactions":tx,"revenue":rev,"is_llm":is_llm})
    seo_by_source.sort(key=lambda x: x["revenue"], reverse=True)
    seo_organic = {k: seo_total[k]-seo_llm[k] for k in seo_total}

    all_rows, _, _ = read_ga4_csv(f"{folder}/all_channels.csv")
    ch_col = "Grupo principal de canais da sessão (Grupo de Canais)"
    channels = []
    for row in all_rows:
        channels.append({
            "channel":      row.get(ch_col,"").strip(),
            "sessions":     int(_n(row.get("Sessões",0))),
            "new_users":    int(_n(row.get("Novos usuários",0))),
            "returning":    int(_n(row.get("Usuários recorrentes",0))),
            "transactions": int(_n(row.get("Transações",0))),
            "revenue":      round(_n(row.get("Receita total",0)),2),
        })
    channels.sort(key=lambda x: x["revenue"], reverse=True)
    total_all = {
        "sessions":     sum(c["sessions"]     for c in channels),
        "transactions": sum(c["transactions"] for c in channels),
        "revenue":      sum(c["revenue"]      for c in channels),
    }

    sessions = seo_total["sessions"]
    trans    = seo_total["transactions"]
    output["ga4"] = {
        "source":            "csv",
        "period_start":      p_s, "period_end": p_e,
        "sessions":          sessions,          "sessions_delta":    0.0,
        "new_users":         seo_total["new_users"],  "new_users_delta":   0.0,
        "returning_users":   seo_total["returning"],  "returning_delta":   0.0,
        "transactions":      trans,             "transactions_delta":0.0,
        "revenue":           round(seo_total["revenue"],2), "revenue_delta": 0.0,
        "revenue_ytd":       round(seo_total["revenue"],2),
        "daily_sessions":    [],
        "channels":          channels,
        "total_all":         total_all,
        "seo_total":         seo_total,
        "seo_organic":       seo_organic,
        "seo_llm":           seo_llm,
        "seo_by_source":     seo_by_source,
        "top_routes":        [],
        "conv_rate":         round(trans/sessions*100,2) if sessions else 0,
    }


# ─── GSC ──────────────────────────────────────────────────────────────────────
def parse_gsc_csvs(folder="gsc"):
    with open(f"{folder}/Gráfico.csv", encoding="utf-8") as f:
        daily_rows = list(csv_module.DictReader(f))
    daily_rows.sort(key=lambda x: x["Data"])
    last_date  = datetime.strptime(daily_rows[-1]["Data"],"%Y-%m-%d").date()
    cur_end    = last_date
    cur_start  = cur_end  - timedelta(days=29)
    prev_end   = cur_start - timedelta(days=1)
    prev_start = prev_end  - timedelta(days=29)
    cur_rows  = [r for r in daily_rows if cur_start.isoformat()  <= r["Data"] <= cur_end.isoformat()]
    prev_rows = [r for r in daily_rows if prev_start.isoformat() <= r["Data"] <= prev_end.isoformat()]

    def stats(rows):
        if not rows: return {"clicks":0,"impressions":0,"ctr":0.0,"position":0.0}
        c = sum(int(r["Cliques"]) for r in rows)
        i = sum(int(r["Impressões"]) for r in rows)
        t = round(sum(_n(r["CTR"]) for r in rows)/len(rows),2)
        p = round(sum(_n(r["Posição"]) for r in rows)/len(rows),1)
        return {"clicks":c,"impressions":i,"ctr":t,"position":p}

    cs = stats(cur_rows); ps = stats(prev_rows)

    with open(f"{folder}/Consultas.csv", encoding="utf-8") as f:
        qrows = list(csv_module.DictReader(f))
    top_queries = [{"query":r["Top consultas"],"clicks":int(r["Cliques"]),
                    "impressions":int(r["Impressões"]),"ctr":round(_n(r["CTR"]),2),
                    "position":round(_n(r["Posição"]),1),"pos_delta":0.0} for r in qrows[:20]]

    with open(f"{folder}/Páginas.csv", encoding="utf-8") as f:
        prows = list(csv_module.DictReader(f))
    top_pages = [{"page":r["Páginas principais"].replace(GSC_SITE_URL.rstrip("/"),"") or "/",
                  "clicks":int(r["Cliques"]),"impressions":int(r["Impressões"]),
                  "ctr":round(_n(r["CTR"]),2),"position":round(_n(r["Posição"]),1)}
                 for r in prows[:20]]

    # Coverage
    indexed_pages=0; coverage_urls=[]; indexed_daily=[]
    if os.path.exists(f"{folder}/coverage/Gráfico.csv"):
        with open(f"{folder}/coverage/Gráfico.csv",encoding="utf-8") as f:
            cv = list(csv_module.DictReader(f))
        if cv: indexed_pages=int(_n(cv[-1].get("Páginas afetadas",0)))
        indexed_daily=[int(_n(r.get("Páginas afetadas",0))) for r in cv[-30:]]
    if os.path.exists(f"{folder}/coverage/Tabela.csv"):
        with open(f"{folder}/coverage/Tabela.csv",encoding="utf-8") as f:
            ct=list(csv_module.DictReader(f))
        coverage_urls=[{"url":r.get("URL",""),"last_crawl":r.get("Último rastreamento","")} for r in ct[:20]]

    # CWV
    cwv_issues=[]; cwv_daily_bad=[]; cwv_daily_ok=[]
    if os.path.exists(f"{folder}/cwv/Tabela.csv"):
        with open(f"{folder}/cwv/Tabela.csv",encoding="utf-8") as f:
            cw=list(csv_module.DictReader(f))
        cwv_issues=[{"severity":r.get("Gravidade",""),"issue":r.get("Problema",""),
                     "urls":int(_n(r.get("URLs",0)))} for r in cw]
    if os.path.exists(f"{folder}/cwv/Gráfico.csv"):
        with open(f"{folder}/cwv/Gráfico.csv",encoding="utf-8") as f:
            cg=list(csv_module.DictReader(f))
        cwv_daily_bad=[int(_n(r.get("Ruins",0))) for r in cg[-30:]]
        cwv_daily_ok =[int(_n(r.get("Bom",0)))   for r in cg[-30:]]

    # Backlinks
    backlinks_total=0
    if os.path.exists(f"{folder}/Latest_links.csv"):
        with open(f"{folder}/Latest_links.csv",encoding="utf-8") as f:
            backlinks_total=sum(1 for _ in csv_module.DictReader(f))

    return {
        "source":"csv","period_start":cur_start.isoformat(),"period_end":cur_end.isoformat(),
        "clicks":cs["clicks"],"clicks_delta":pct(cs["clicks"],ps["clicks"]),
        "impressions":cs["impressions"],"impressions_delta":pct(cs["impressions"],ps["impressions"]),
        "ctr":cs["ctr"],"ctr_delta":round(cs["ctr"]-ps["ctr"],2),
        "position":cs["position"],"position_delta":round(ps["position"]-cs["position"],1),
        "top_queries":top_queries[:10],"top_pages":top_pages[:10],"declining_pages":[],
        "daily_clicks":[int(r["Cliques"]) for r in cur_rows],
        "daily_clicks_prev":[int(r["Cliques"]) for r in prev_rows],
        "daily_impressions":[int(r["Impressões"]) for r in cur_rows],
        "all_daily":[{"date":r["Data"],"clicks":int(r["Cliques"]),"impressions":int(r["Impressões"]),
                      "ctr":round(_n(r["CTR"]),2),"position":round(_n(r["Posição"]),1)}
                     for r in daily_rows],
        "data_start":daily_rows[0]["Data"],"data_end":daily_rows[-1]["Data"],
        "indexed_pages":indexed_pages,"indexed_daily":indexed_daily,
        "coverage_urls":coverage_urls,"cwv_issues":cwv_issues,
        "cwv_daily_bad":cwv_daily_bad,"cwv_daily_ok":cwv_daily_ok,
        "backlinks_total":backlinks_total,
    }

def fetch_gsc():
    if os.path.exists("gsc/Gráfico.csv"):
        try:
            output["gsc"] = parse_gsc_csvs("gsc")
            log_ok("GSC (CSV)"); return
        except Exception as e:
            log_err("GSC CSV", traceback.format_exc())
    try:
        svc = build("searchconsole","v1",credentials=creds)
        sc  = svc.searchanalytics()
        def query(s,e,dims=None,limit=25):
            return sc.query(siteUrl=GSC_SITE_URL,body={"startDate":s,"endDate":e,"dimensions":dims or [],"rowLimit":limit}).execute()
        rc=query(p_start,p_end); rp=query(c_start,c_end)
        def kpi(r,k): return r.get("rows",[{}])[0].get(k,0) if r.get("rows") else 0
        cc=int(kpi(rc,"clicks")); ic=int(kpi(rc,"impressions"))
        tc=round(kpi(rc,"ctr")*100,2); pc=round(kpi(rc,"position"),1)
        cp=int(kpi(rp,"clicks")); ip=int(kpi(rp,"impressions"))
        tp=round(kpi(rp,"ctr")*100,2); pp=round(kpi(rp,"position"),1)
        tqc=query(p_start,p_end,["query"],20); tqp=query(c_start,c_end,["query"],20)
        pq={r["keys"][0]:r for r in tqp.get("rows",[])}
        tq=[{"query":r["keys"][0],"clicks":r.get("clicks",0),"impressions":r.get("impressions",0),
             "ctr":round(r.get("ctr",0)*100,2),"position":round(r.get("position",99),1),
             "pos_delta":round(pq.get(r["keys"][0],{}).get("position",r["position"])-r["position"],1)}
            for r in tqc.get("rows",[])]
        dqc=query(p_start,p_end,["date"],31); dqp=query(c_start,c_end,["date"],31)
        dc=sorted(dqc.get("rows",[]),key=lambda x:x["keys"][0])
        dp=sorted(dqp.get("rows",[]),key=lambda x:x["keys"][0])
        output["gsc"]={"clicks":cc,"clicks_delta":pct(cc,cp),"impressions":ic,
            "impressions_delta":pct(ic,ip),"ctr":tc,"ctr_delta":round(tc-tp,2),
            "position":pc,"position_delta":round(pp-pc,1),"top_queries":tq[:10],
            "top_pages":[],"declining_pages":[],"daily_clicks":[r["clicks"] for r in dc],
            "daily_clicks_prev":[r["clicks"] for r in dp],"daily_impressions":[r["impressions"] for r in dc],
            "all_daily":[],"data_start":p_start,"data_end":p_end}
        log_ok("GSC (API)")
    except Exception as e:
        log_err("GSC", traceback.format_exc())

# ─── YOUTUBE ──────────────────────────────────────────────────────────────────
def fetch_youtube():
    output["youtube"]={"views":0,"views_delta":0,"watch_time":0,
                        "subs_gained":0,"subs_lost":0,"status":"pending_channel_link"}
    log_ok("YouTube (pendente vinculação)")

# ─── PLAY ─────────────────────────────────────────────────────────────────────
def fetch_play():
    output["play"]={"status":"pending_permission"}
    log_ok("Play Console (stand by)")

# ─── SEMRUSH ──────────────────────────────────────────────────────────────────
def fetch_semrush():
    if not SEMRUSH_KEY:
        output["semrush"]={"error":"no key"}; return
    try:
        base="https://api.semrush.com/"
        def sem(p):
            p["key"]=SEMRUSH_KEY
            r=requests.get(base,params=p,timeout=20); r.raise_for_status(); return r.text
        # Testar key antes com chamada simples
        test = sem({"type":"domain_rank","domain":SEMRUSH_DOMAIN,"database":"br","export_columns":"Or,Ot,Et"})
        print(f"    Semrush test: {test[:80]}")
        kw_raw=sem({"type":"domain_organic","domain":SEMRUSH_DOMAIN,"database":"br",
                    "display_limit":5000,"export_columns":"Ph,Po,Nq,Tr,Fk"})
        lines=[l.split(";") for l in kw_raw.strip().split("\n")[1:] if l]
        top1=top3=top10=top20=serp_ai=serp_fs=serp_paa=serp_sl=0
        for p in lines:
            if len(p)<2: continue
            try:
                pos=int(p[1]); feats=p[4] if len(p)>4 else ""
                if pos==1:  top1+=1
                if pos<=3:  top3+=1
                if pos<=10: top10+=1
                if pos<=20: top20+=1
                if "28" in feats: serp_ai+=1
                if "2"  in feats: serp_fs+=1
                if "8"  in feats: serp_paa+=1
                if "4"  in feats: serp_sl+=1
            except: pass
        total=len(lines)
        comp_data={}
        for comp in COMPETITORS:
            time.sleep(0.5)
            raw=sem({"type":"domain_organic","domain":comp,"database":"br",
                     "display_limit":1,"export_columns":"Or,Ot"})
            cl=[l.split(";") for l in raw.strip().split("\n") if l]
            kws=traffic=0
            if len(cl)>1 and len(cl[1])>=2:
                try: kws=int(cl[1][0] or 0)
                except: pass
                try: traffic=int(cl[1][1] or 0)
                except: pass
            comp_data[comp]={"keywords":kws,"traffic":traffic}
        my_raw=sem({"type":"domain_organic","domain":SEMRUSH_DOMAIN,"database":"br",
                    "display_limit":1,"export_columns":"Or,Ot"})
        my_cl=[l.split(";") for l in my_raw.strip().split("\n") if l]
        my_t=0
        if len(my_cl)>1 and len(my_cl[1])>=2:
            try: my_t=int(my_cl[1][1] or 0)
            except: pass
        comp_data[SEMRUSH_DOMAIN]={"keywords":total,"traffic":my_t}
        output["semrush"]={
            "total_keywords":total,"top1":top1,"top3":top3,"top10":top10,"top20":top20,
            "rank_distribution":[top1,top3-top1,top10-top3,top20-top10,total-top20],
            "serp_features":{"ai_overview":serp_ai,"featured_snippet":serp_fs,
                             "people_also_ask":serp_paa,"sitelinks":serp_sl},
            "competitors":comp_data,
        }
        log_ok("Semrush")
    except requests.exceptions.HTTPError as e:
        body = e.response.text[:300] if hasattr(e,'response') and e.response else ''
        log_err("Semrush", f"HTTP {e} | body: {body}")
    except Exception as e:
        log_err("Semrush", traceback.format_exc())

# ─── GTMETRIX ─────────────────────────────────────────────────────────────────
def fetch_gtmetrix():
    if not GTMETRIX_KEY:
        output["gtmetrix"]={"error":"no key"}; return
    try:
        pages=[{"url":f"{GSC_SITE_URL}","layout":"home"},
               {"url":f"{GSC_SITE_URL}passagem-onibus","layout":"listagem"}]
        results=[]
        for p in pages:
            r=requests.post("https://gtmetrix.com/api/2.0/tests",auth=(GTMETRIX_KEY,""),
                            json={"data":{"type":"test","attributes":{"url":p["url"]}}},timeout=15)
            if r.status_code==202:
                tid=r.json()["data"]["id"]
                for _ in range(12):
                    time.sleep(5)
                    tr=requests.get(f"https://gtmetrix.com/api/2.0/tests/{tid}",
                                    auth=(GTMETRIX_KEY,""),timeout=15).json()
                    state=tr["data"]["attributes"].get("state")
                    if state=="completed":
                        a=tr["data"]["attributes"]
                        results.append({"layout":p["layout"],"url":p["url"],
                            "score":a.get("gtmetrix_grade"),
                            "performance":round(a.get("performance_score",0)*100),
                            "lcp":a.get("largest_contentful_paint"),
                            "cls":a.get("cumulative_layout_shift"),
                            "inp":a.get("interaction_to_next_paint")})
                        break
                    elif state=="error": break
        output["gtmetrix"]={"pages":results}
        log_ok("GTmetrix")
    except Exception as e:
        log_err("GTmetrix", traceback.format_exc())

def fetch_ga4():
    # Primário: API
    try:
        fetch_ga4_api()
        log_ok("GA4 (API)")
        return
    except Exception as e:
        log_err("GA4 API", traceback.format_exc())
    # Fallback: CSVs segmentados
    if os.path.exists("ga4/seo_traffic.csv"):
        try:
            fetch_ga4_csv()
            log_ok("GA4 (CSV)")
            return
        except Exception as e:
            log_err("GA4 CSV", traceback.format_exc())

# ─── GA4 CSV GENÉRICO (Blog / Viva) ──────────────────────────────────────────
def fetch_ga4_csv_generic(folder, label, prefix=""):
    """
    Lê CSVs de uma propriedade secundária (Blog ou Viva).
    Suporta prefixo nos nomes de arquivo (ex: ga4_seo_traffic.csv).
    """
    seo_file  = f"{folder}/{prefix}seo_traffic.csv"
    all_file  = f"{folder}/{prefix}all_channels.csv"
    page_file = f"{folder}/{prefix}top_pages.csv"

    result = {"source":"csv","period_start":"","period_end":"",
              "sessions":0,"new_users":0,"returning_users":0,
              "transactions":0,"revenue":0.0,"revenue_ytd":0.0,
              "conv_rate":0.0,"top_pages":[],"channels":[],
              "total_all":{},"seo_total":{},"seo_llm":{},"seo_by_source":[]}

    # SEO traffic
    if os.path.exists(seo_file):
        rows, p_s, p_e = read_ga4_csv(seo_file)
        src_col = "Origem / mídia da sessão"
        total = {"sessions":0,"new_users":0,"returning":0,"transactions":0,"revenue":0.0}
        llm   = {"sessions":0,"new_users":0,"returning":0,"transactions":0,"revenue":0.0}
        by_src = []
        for row in rows:
            src = row.get(src_col,"").strip()
            s   = int(_n(row.get("Sessões",0)))
            nu  = int(_n(row.get("Novos usuários",0)))
            ret = int(_n(row.get("Usuários recorrentes",0)))
            tx  = int(_n(row.get("Transações",0)))
            rev = round(_n(row.get("Receita total",0)),2)
            for k,v in [("sessions",s),("new_users",nu),("returning",ret),("transactions",tx)]:
                total[k] += v
            total["revenue"] += rev
            is_llm = src in LLM_SOURCES
            if is_llm:
                for k,v in [("sessions",s),("new_users",nu),("returning",ret),("transactions",tx)]:
                    llm[k] += v
                llm["revenue"] += rev
            by_src.append({"source":src,"sessions":s,"transactions":tx,"revenue":rev,"is_llm":is_llm})
        by_src.sort(key=lambda x: x["revenue"], reverse=True)

        # Detectar gap de dados (muitos zeros consecutivos = período sem tracking)
        data_gap = total["sessions"] == 0
        sess = total["sessions"]
        trans = total["transactions"]
        result.update({
            "period_start": p_s, "period_end": p_e,
            "sessions": sess, "new_users": total["new_users"],
            "returning_users": total["returning"],
            "transactions": trans, "revenue": round(total["revenue"],2),
            "revenue_ytd": round(total["revenue"],2),
            "conv_rate": round(trans/sess*100,2) if sess else 0,
            "seo_total": total, "seo_llm": llm, "seo_by_source": by_src,
            "data_gap": data_gap,
        })
        log_ok(f"GA4 {label} SEO (CSV){' — ATENÇÃO: zero sessões, verificar gap de tracking' if data_gap else ''}")

    # All channels
    if os.path.exists(all_file):
        rows, _, _ = read_ga4_csv(all_file)
        ch_col = "Grupo principal de canais da sessão (Grupo de Canais)"
        channels = [{"channel":r.get(ch_col,"").strip(),
                     "sessions":int(_n(r.get("Sessões",0))),
                     "transactions":int(_n(r.get("Transações",0))),
                     "revenue":round(_n(r.get("Receita total",0)),2)} for r in rows]
        channels.sort(key=lambda x: x["revenue"], reverse=True)
        result["channels"] = channels
        result["total_all"] = {"sessions":sum(c["sessions"] for c in channels),
                               "transactions":sum(c["transactions"] for c in channels),
                               "revenue":sum(c["revenue"] for c in channels)}

    # Top pages
    if os.path.exists(page_file):
        rows, _, _ = read_ga4_csv(page_file)
        col = next((k for k in (rows[0] if rows else {}).keys()
                    if "página" in k.lower() or "caminho" in k.lower()), "")
        result["top_pages"] = sorted([{
            "path":     r.get(col,""),
            "sessions": int(_n(r.get("Sessões",0))),
            "revenue":  round(_n(r.get("Receita total",0)),2),
        } for r in rows], key=lambda x: x["sessions"], reverse=True)[:10]

    return result

# ─── GA4 BLOG ─────────────────────────────────────────────────────────────────
def fetch_ga4_property(property_id, label):
    """Busca KPIs básicos de uma propriedade GA4."""
    try:
        client = BetaAnalyticsDataClient(credentials=creds)
        r = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name=m) for m in ["sessions","newUsers","purchaseRevenue","transactions"]],
            date_ranges=[
                DateRange(start_date=p_start, end_date=p_end),
                DateRange(start_date=c_start, end_date=c_end),
            ],
            limit=10,
        ))
        def gv(rows, dr, mi):
            row = next((r for r in rows if r.dimension_values[0].value == dr), None)
            return float(row.metric_values[mi].value) if row else 0.0

        sessions  = int(gv(r.rows, "date_range_0", 0))
        new_users = int(gv(r.rows, "date_range_0", 1))
        revenue   = round(gv(r.rows, "date_range_0", 2), 2)
        trans     = int(gv(r.rows, "date_range_0", 3))
        p_sess    = int(gv(r.rows, "date_range_1", 0))
        p_rev     = round(gv(r.rows, "date_range_1", 2), 2)

        # YTD
        r_ytd = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name="purchaseRevenue")],
            date_ranges=[DateRange(start_date=ytd_start, end_date=p_end)],
            limit=1,
        ))
        revenue_ytd = round(float(r_ytd.rows[0].metric_values[0].value), 2) if r_ytd.rows else 0.0

        # Top páginas
        r2 = client.run_report(RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name="sessions"), Metric(name="purchaseRevenue")],
            dimensions=[Dimension(name="pagePath")],
            date_ranges=[DateRange(start_date=p_start, end_date=p_end)],
            limit=10,
        ))
        top_pages = sorted([{
            "path": row.dimension_values[0].value,
            "sessions": int(row.metric_values[0].value),
            "revenue": round(float(row.metric_values[1].value), 2),
        } for row in r2.rows], key=lambda x: x["sessions"], reverse=True)

        result = {
            "source": "api", "period_start": p_start, "period_end": p_end,
            "sessions": sessions, "sessions_delta": pct(sessions, p_sess),
            "new_users": new_users, "transactions": trans,
            "revenue": revenue, "revenue_delta": pct(revenue, p_rev),
            "revenue_ytd": revenue_ytd,
            "conv_rate": round(trans/sessions*100, 2) if sessions else 0,
            "top_pages": top_pages,
        }
        log_ok(f"GA4 {label} (API)")
        return result
    except Exception as e:
        log_err(f"GA4 {label}", traceback.format_exc())
        return {}

def fetch_gsc_property(site_url, csv_folder, label):
    """Busca dados GSC de uma propriedade via CSV ou API."""
    # Tenta CSV primeiro
    if csv_folder and os.path.exists(f"{csv_folder}/Gráfico.csv"):
        try:
            result = parse_gsc_csvs(csv_folder)
            log_ok(f"GSC {label} (CSV)")
            return result
        except Exception as e:
            log_err(f"GSC {label} CSV", str(e))
    # Tenta API
    try:
        svc = build("searchconsole", "v1", credentials=creds)
        sc  = svc.searchanalytics()
        def query(s, e, dims=None, limit=20):
            return sc.query(siteUrl=site_url,
                body={"startDate":s,"endDate":e,"dimensions":dims or [],"rowLimit":limit}).execute()
        rc = query(p_start, p_end)
        rp = query(c_start, c_end)
        def kpi(r, k): return r.get("rows",[{}])[0].get(k,0) if r.get("rows") else 0
        tq = query(p_start, p_end, ["query"], 20)
        top_queries = [{"query":r["keys"][0],"clicks":r.get("clicks",0),
                        "impressions":r.get("impressions",0),
                        "ctr":round(r.get("ctr",0)*100,2),
                        "position":round(r.get("position",99),1)} for r in tq.get("rows",[])]
        result = {
            "source": "api", "period_start": p_start, "period_end": p_end,
            "clicks": int(kpi(rc,"clicks")), "clicks_delta": pct(int(kpi(rc,"clicks")), int(kpi(rp,"clicks"))),
            "impressions": int(kpi(rc,"impressions")), "ctr": round(kpi(rc,"ctr")*100,2),
            "position": round(kpi(rc,"position"),1),
            "top_queries": top_queries[:10], "top_pages": [], "all_daily": [],
        }
        log_ok(f"GSC {label} (API)")
        return result
    except Exception as e:
        log_err(f"GSC {label}", traceback.format_exc())
        return {}

# ─── GA4 YTD YoY ─────────────────────────────────────────────────────────────
def parse_ytd_yoy(filepath="ga4/ytd_yoy.csv"):
    """
    Lê CSV do GA4 com dois períodos (YTD atual vs YTD anterior).
    Estrutura: dois blocos separados por '# Data de início:'
    Retorna (revenue_current, revenue_previous, sessions_cur, sessions_prv)
    """
    with open(filepath, encoding="utf-8-sig") as f:
        raw = f.read()

    sections = []
    current_lines = []
    current_date = None

    for line in raw.replace("
", "
").split("
"):
        if "Data de início:" in line:
            if current_lines and current_date:
                sections.append((current_date, current_lines))
            current_lines = []
            d = line.split(":")[-1].strip()
            current_date = f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d
        elif not line.startswith("#") and line.strip():
            current_lines.append(line)

    if current_lines and current_date:
        sections.append((current_date, current_lines))

    results = {}
    for start_date, lines in sections:
        year = start_date[:4]
        reader = csv_module.DictReader(lines)
        rows = list(reader)
        rev  = sum(_n(r.get("Receita total", 0)) for r in rows)
        sess = sum(int(_n(r.get("Sessões", 0))) for r in rows)
        results[year] = {"revenue": round(rev, 2), "sessions": sess, "start": start_date}

    cur_year = str(date.today().year)
    prv_year = str(date.today().year - 1)
    return (
        results.get(cur_year, {}).get("revenue", 0),
        results.get(prv_year, {}).get("revenue", 0),
        results.get(cur_year, {}).get("sessions", 0),
        results.get(prv_year, {}).get("sessions", 0),
    )

# ─── RUN ──────────────────────────────────────────────────────────────────────
print("\n── Buscando dados ──────────────────────────────")
fetch_ga4()
fetch_gsc()
# ── Agrega impressões/cliques de propriedades GSC extras ──
gsc_extra = {}
for graf, name in GSC_EXTRA_FILES.items():
    if os.path.exists(graf):
        try:
            with open(graf, encoding="utf-8") as f:
                rows = list(csv_module.DictReader(f))
            rows.sort(key=lambda x: x.get("Data",""))
            key = graf.replace("/","_").replace(".csv","")
            gsc_extra[key] = {
                "name": name,
                "all_daily": [{"date":r["Data"],"clicks":int(_n(r["Cliques"])),
                                "impressions":int(_n(r["Impressões"]))}
                               for r in rows if r.get("Data")],
            }
            log_ok(f"GSC extra — {name}")
        except Exception as e:
            log_err(f"GSC extra {graf}", str(e))
output["gsc"]["extra_properties"] = gsc_extra

# ── YTD YoY — ytd_previous.csv = mesmo período do ano anterior (ex: 01/01/2025 → 24/05/2025) ──
for ytd_file, ytd_key in [("ga4/ytd_previous.csv","revenue_ytd_prev"),
                           ("ga4/ytd_current.csv","revenue_ytd")]:
    if os.path.exists(ytd_file):
        try:
            rows, p_s, p_e = read_ga4_csv(ytd_file)
            rev = sum(_n(r.get("Receita total",0)) for r in rows)
            output["ga4"][ytd_key] = round(rev, 2)
            log_ok(f"GA4 {ytd_key} (CSV) — {p_s} → {p_e} — R$ {rev:,.0f}")
        except Exception as e:
            log_err(f"GA4 {ytd_file}", str(e))

fetch_youtube()
fetch_play()
fetch_semrush()
fetch_gtmetrix()

# ── Rotas ──
if os.path.exists("ga4/routes.csv"):
    try:
        rows, _, _ = read_ga4_csv("ga4/routes.csv")
        col = next((k for k in (rows[0] if rows else {}).keys()
                    if "página" in k.lower() or "caminho" in k.lower() or "page" in k.lower()), "")
        output["ga4"]["top_routes"] = sorted([{
            "path":     r.get(col,""),
            "sessions": int(_n(r.get("Sessões",0))),
            "revenue":  round(_n(r.get("Receita total",0)),2),
        } for r in rows if r.get(col,"")], key=lambda x: x["sessions"], reverse=True)[:20]
        log_ok("GA4 routes (CSV)")
    except Exception as e:
        log_err("GA4 routes", str(e))

# ── Viações — filtro por marca nas URLs ──
CARRIER_TERMS = ["util","sampaio","real-expresso","real_expresso",
                 "rapido-federal","rapido_federal","brisa",
                 "guanabara","viacao"]
if os.path.exists("ga4/carriers.csv"):
    try:
        rows, _, _ = read_ga4_csv("ga4/carriers.csv")
        col = next((k for k in (rows[0] if rows else {}).keys()
                    if "página" in k.lower() or "caminho" in k.lower() or "page" in k.lower() or "url" in k.lower()), "")
        carriers = []
        for r in rows:
            url = r.get(col,"").lower()
            if any(t in url for t in CARRIER_TERMS):
                carriers.append({
                    "path":     r.get(col,""),
                    "sessions": int(_n(r.get("Sessões",0))),
                    "users":    int(_n(r.get("Usuários ativos",r.get("Total de usuários",0)))),
                    "revenue":  round(_n(r.get("Receita total",0)),2),
                })
        carriers.sort(key=lambda x: x["sessions"], reverse=True)
        output["ga4"]["top_carriers"] = carriers[:20]
        log_ok(f"GA4 carriers (CSV) — {len(carriers)} páginas de viação encontradas")
    except Exception as e:
        log_err("GA4 carriers", str(e))

# ── Blog ──
blog_ga4 = {}
if os.path.exists("ga4_blog/seo_traffic.csv"):
    try:
        blog_ga4 = fetch_ga4_csv_generic("ga4_blog", "Blog")
    except Exception as e:
        log_err("GA4 Blog CSV", str(e))
if not blog_ga4:
    blog_ga4 = fetch_ga4_property(GA4_BLOG_PROPERTY_ID, "Blog")

output["blog"] = {
    "ga4": blog_ga4,
    "gsc": fetch_gsc_property(GSC_BLOG_URL, "gsc_blog", "Blog"),
}

# ── Viva — estrutura viva/ga4_*.csv ──
viva_ga4 = {}
if os.path.exists("viva/ga4_seo_traffic.csv"):
    try:
        viva_ga4 = fetch_ga4_csv_generic("viva", "Viva", prefix="ga4_")
    except Exception as e:
        log_err("GA4 Viva CSV", str(e))
if not viva_ga4:
    viva_ga4 = fetch_ga4_property(GA4_VIVA_PROPERTY_ID, "Viva")

output["viva"] = {
    "ga4": viva_ga4,
    "gsc": fetch_gsc_property(GSC_VIVA_URL, "gsc_viva", "Viva"),
}

with open("data.json","w",encoding="utf-8") as f:
    json.dump(output,f,ensure_ascii=False,indent=2)

print(f"\n── Concluído · erros: {len(output['errors'])} ──────────────────")
for e in output["errors"]: print(f"   • {e[:120]}")
# Só falha se não temos dados de GA4 nem de GSC de nenhuma fonte
ga4_ok  = bool(output.get("ga4",{}).get("sessions") or output.get("ga4",{}).get("source"))
gsc_ok  = bool(output.get("gsc",{}).get("clicks") is not None)
if not ga4_ok or not gsc_ok:
    print("   CRÍTICO: GA4 ou GSC sem dados")
    sys.exit(1)
sys.exit(0)
