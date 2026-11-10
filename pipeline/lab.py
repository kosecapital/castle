#!/usr/bin/env python3
"""Yoklama betiği: bu makineden veri kaynaklarına ulaşılıyor mu, hangi alanlar var?

Her adrese tek istek atar; engellenirse hatayı yazar ve geçer (yeniden denemez, başka yol aramaz).
Çıktı: data/_probe/lab.txt ve yanındaki dosyalar.   Kullanım: python3 pipeline/lab.py
"""
import json, os, sys, collections, datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collect import HEADERS, COLUMNS

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "_probe")
os.makedirs(OUT, exist_ok=True)
log = ["çalıştırma: " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")]
def say(*a):
    s = " ".join(str(x) for x in a); print(s); log.append(s)
def post(url, body):
    return requests.post(url, headers=HEADERS, json=body, timeout=60)
FILT = [{"left": "is_primary", "operation": "equal", "right": True}, {"left": "type", "operation": "equal", "right": "stock"},
        {"left": "typespecs", "operation": "has", "right": ["common"]}]

# 0) erişim: her adrese tek istek
reach = {}
for name, fn in (
    ("scanner.tradingview.com", lambda: post("https://scanner.tradingview.com/turkey/scan", {"columns": ["name", "close"], "range": [0, 1]}).status_code),
    ("stockanalysis.com", lambda: requests.get("https://stockanalysis.com/quote/ist/FROTO/financials/ratios/", headers={"user-agent": HEADERS["user-agent"]}, timeout=60).status_code),
    ("api.worldbank.org", lambda: requests.get("https://api.worldbank.org/v2/country/TUR/indicator/FP.CPI.TOTL.ZG?format=json&date=2024:2025", timeout=60).status_code),
    ("www.imf.org", lambda: requests.get("https://www.imf.org/external/datamapper/api/v1/PCPIEPCH/TUR?periods=2025", headers={"user-agent": HEADERS["user-agent"]}, timeout=60).status_code),
):
    try:
        reach[name] = fn()
    except Exception as e:
        reach[name] = "ENGEL/HATA: " + type(e).__name__ + " " + str(e)[:160]
    say("erişim", name, "->", reach[name])
ok_tv = reach.get("scanner.tradingview.com") == 200

if ok_tv:
    # 1) alan listesi
    for method in ("GET", "POST"):
        try:
            r = requests.request(method, "https://scanner.tradingview.com/turkey/metainfo", headers=HEADERS, json=({} if method == "POST" else None), timeout=60)
            say("metainfo", method, r.status_code, len(r.text))
            if r.status_code == 200:
                j = r.json(); fields = j.get("fields") if isinstance(j, dict) else j
                open(os.path.join(OUT, "fields.txt"), "w").write("\n".join(f'{f.get("n")}\t{f.get("t")}' for f in fields))
                say("alan sayısı", len(fields)); say("  _h ile bitenler:", " ".join(sorted(f["n"] for f in fields if str(f.get("n", "")).endswith("_h"))))
                break
        except Exception as e:
            say("metainfo", method, "HATA", repr(e)[:200])

    # 2) aday alan adları: beş hisse üzerinde hangileri dolu
    CAND = """total_equity_fy_h shrhldrs_equity_fy_h total_shrhldrs_equity_fy_h common_equity_total_fy_h book_value_per_share_fy_h total_assets_fy_h
total_liabilities_fy_h net_debt_fy_h cash_n_equivalents_fy_h cash_n_short_term_invest_fy_h total_revenue_fy_h earnings_per_share_basic_fy_h
dps_common_stock_prim_issue_fy_h capital_expenditures_unchanged_fy_h return_on_equity_fy_h return_on_invested_capital_fy_h fiscal_period_fy_h
fiscal_period_end_fh_h net_income_ttm_h net_income_fq_h total_assets_fq_h total_debt_fq_h net_income_ttm free_cash_flow_ttm ebitda_ttm ebitda_fy
net_debt_fq net_debt_fy total_debt_fq total_debt_fy total_liabilities_fy total_liabilities_fq total_assets_fy total_assets_fq
shrhldrs_equity_fq shrhldrs_equity_fy total_equity_fq total_equity_fy book_value_per_share_fq book_value_per_share_fy
return_on_equity return_on_equity_fq return_on_equity_fy return_on_common_equity_fy return_on_common_equity_ttm return_on_invested_capital_fy
net_debt_to_ebitda_fq net_debt_to_ebitda_fy debt_to_equity_fq total_assets_to_equity_fy price_earnings_ttm price_book_fq price_book_ratio
dividends_yield dividends_yield_current dividends_yield_fy dividend_payout_ratio_fy dividend_payout_ratio_ttm dividend_payout_ratio_percent_fy
fiscal_period_current fiscal_period_end_current fiscal_period_end_fy fiscal_period_end_fq fiscal_period_fy most_recent_quarter_date
earnings_release_date earnings_release_trading_date_fq earnings_release_trading_date_fy float_shares_percent_current
exchange country currency fundamental_currency_code is_primary type typespecs isin submarket update_mode""".split()
    try:
        r = post("https://scanner.tradingview.com/global/scan", {"symbols": {"tickers": ["BIST:FROTO", "BIST:AKBNK", "NASDAQ:AAPL", "TSE:7203", "LSE:ULVR"]},
                                                                   "columns": CAND, "ignore_unknown_fields": True})
        say("aday sorgusu", r.status_code)
        rows = {row["s"]: dict(zip(CAND, row["d"])) for row in r.json().get("data", [])}
        json.dump(rows, open(os.path.join(OUT, "cand.json"), "w"), ensure_ascii=False, indent=1)
        for c in CAND:
            say(f"  {c:38}", " | ".join(str(rows[s].get(c))[:30] for s in rows))
    except Exception as e:
        say("aday sorgusu HATA", repr(e)[:300])

    # 3) ABD: borsa dağılımı (tezgâh üstü hisseler ayrılacak mı?)
    try:
        r = post("https://scanner.tradingview.com/america/scan", {"markets": ["america"], "columns": ["name", "exchange", "market_cap_basic", "price_earnings_ttm", "country"],
                                                                   "filter": FILT, "range": [0, 20000], "ignore_unknown_fields": True})
        j = r.json(); rows = [dict(zip(["name", "exchange", "m", "pe", "country"], x["d"])) for x in j["data"]]
        cnt = collections.Counter(x["exchange"] for x in rows)
        say("america toplam", j["totalCount"], dict(cnt))
        for ex in cnt:
            sub = [x for x in rows if x["exchange"] == ex]
            say("   ", ex, "| F/K dolu", sum(1 for x in sub if x["pe"]), "| ≥60 mn $", sum(1 for x in sub if (x["m"] or 0) >= 6e7))
        say("    ülke (ilk 8):", collections.Counter(x["country"] for x in rows).most_common(8))
    except Exception as e:
        say("america HATA", repr(e)[:300])

    # 4) döviz ve enflasyon TradingView'de var mı
    for url, tick in (("https://scanner.tradingview.com/forex/scan", ["FX_IDC:USDTRY", "FX_IDC:USDJPY", "FX_IDC:USDEUR", "FX_IDC:USDCNY", "FX_IDC:USDTWD", "FX_IDC:USDKRW"]),
                      ("https://scanner.tradingview.com/global/scan", ["FX_IDC:USDTRY", "ECONOMICS:TRIRYY", "ECONOMICS:USIRYY", "ECONOMICS:JPIRYY"]),
                      ("https://scanner.tradingview.com/economics/scan", ["ECONOMICS:TRIRYY", "ECONOMICS:USIRYY"])):
        try:
            r = post(url, {"symbols": {"tickers": tick}, "columns": ["close", "description", "name", "currency"], "ignore_unknown_fields": True})
            say(url.split("/")[3], r.status_code, r.text[:600])
        except Exception as e:
            say(url, "HATA", repr(e)[:200])

    # 5) Türkiye: bütün satırlar (diziler son 7 yıla kırpılmış): elle toplanan taban veriyle karşılaştırma için
    try:
        r = post("https://scanner.tradingview.com/turkey/scan", {"markets": ["turkey"], "columns": COLUMNS + ["total_assets_fy_h", "total_revenue_fy_h", "dps_common_stock_prim_issue_fy_h"],
                                                                  "filter": FILT, "range": [0, 20000], "ignore_unknown_fields": True,
                                                                  "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}})
        cols = ["ticker"] + COLUMNS + ["total_assets_fy_h", "total_revenue_fy_h", "dps_common_stock_prim_issue_fy_h"]
        rows = [dict(zip(cols, [x["s"]] + x["d"])) for x in r.json()["data"]]
        for x in rows:
            for k, v in list(x.items()):
                if isinstance(v, list) and k.endswith("_h"):
                    x[k] = v[:7]
        json.dump(rows, open(os.path.join(OUT, "turkey_scan.json"), "w"), ensure_ascii=False, separators=(",", ":"))
        say("turkey_scan.json", len(rows), "satır")
    except Exception as e:
        say("turkey HATA", repr(e)[:300])

# 6) enflasyon kaynakları ve yedek oran sayfası (ulaşılabiliyorsa)
for name, url in (("worldbank", "https://api.worldbank.org/v2/country/TUR;USA;JPN/indicator/FP.CPI.TOTL.ZG?format=json&date=2020:2026&per_page=200"),
                  ("imf", "https://www.imf.org/external/datamapper/api/v1/PCPIEPCH/TUR/USA/JPN?periods=2021,2022,2023,2024,2025,2026"),
                  ("stockanalysis", "https://stockanalysis.com/quote/ist/FROTO/financials/ratios/")):
    host = {"worldbank": "api.worldbank.org", "imf": "www.imf.org", "stockanalysis": "stockanalysis.com"}[name]
    if reach.get(host) != 200:
        continue
    try:
        r = requests.get(url, headers={"user-agent": HEADERS["user-agent"]}, timeout=60)
        say(name, r.status_code, len(r.text))
        open(os.path.join(OUT, name + (".html" if name == "stockanalysis" else ".json")), "w").write(r.text)
        if name != "stockanalysis":
            say("   ", r.text[:400].replace("\n", " "))
        else:
            say("    'Return on Equity' sayfada var mı:", "Return on Equity" in r.text)
    except Exception as e:
        say(name, "HATA", repr(e)[:200])

open(os.path.join(OUT, "lab.txt"), "w").write("\n".join(log) + "\n")
