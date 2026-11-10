#!/usr/bin/env python3
"""Yoklama betiği (2. tur): İş Yatırım tablosu, enflasyon kaynağı, stockanalysis adres kalıpları ve hız sınırı, aday sayıları.

Her adrese sınırlı sayıda istek atar; engellenirse hatayı yazar ve geçer.
Çıktı: data/_probe/lab2.txt   Kullanım: python3 pipeline/lab.py
"""
import json, os, re, sys, time, html, collections, datetime
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collect import HEADERS

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "_probe")
os.makedirs(OUT, exist_ok=True)
UA = {"user-agent": HEADERS["user-agent"], "accept-language": "tr-TR,tr;q=0.9,en;q=0.8"}
log = ["çalıştırma: " + datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")]
def say(*a):
    s = " ".join(str(x) for x in a); print(s); log.append(s)
def cells(row):
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.S)]

# 1) İş Yatırım: temel değerler ve oranlar sayfası
try:
    r = requests.get("https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx", headers=UA, timeout=90)
    s = r.text
    say("isyatirim", r.status_code, len(s))
    tables = re.findall(r"<table(.*?)>(.*?)</table>", s, flags=re.S)
    say("  tablo sayısı", len(tables))
    for attr, body in tables:
        rows = re.findall(r"<tr.*?</tr>", body, flags=re.S)
        tid = re.search(r'id="([^"]+)"', attr)
        say("  tablo", tid.group(1) if tid else "-", "satır", len(rows))
        for row in rows[:3]:
            say("     ", " ; ".join(cells(row))[:330])
    for m in re.findall(r'id="(temel[^"]*)"', s)[:30]:
        say("  id", m)
    for m in sorted(set(re.findall(r"(/_layouts/[^\"' )]+)", s)))[:25]:
        say("  uç", m[:200])
    i = s.find("FROTO"); say("  FROTO çevresi:", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", ";", s[max(0, i - 200):i + 700]))[:700] if i >= 0 else "yok")
except Exception as e:
    say("isyatirim HATA", repr(e)[:300])

# 2) yıl sonu enflasyonu: DBnomics üzerinden IMF WEO (PCPIEPCH = dönem sonu TÜFE değişimi)
for url in ("https://api.db.nomics.world/v22/series/IMF/WEO:latest/TUR.PCPIEPCH.pcent_change?observations=1",
            "https://api.db.nomics.world/v22/series?series_ids=IMF/WEO:latest/USA.PCPIEPCH.pcent_change,IMF/WEO:latest/JPN.PCPIEPCH.pcent_change&observations=1"):
    try:
        r = requests.get(url, headers=UA, timeout=60)
        say("dbnomics", r.status_code, len(r.text))
        j = r.json()
        for d in j.get("series", {}).get("docs", []):
            per, val = d.get("period", []), d.get("value", [])
            say("   ", d.get("series_code"), d.get("dataset_code"), dict(list(zip(per, val))[-9:]))
    except Exception as e:
        say("dbnomics HATA", repr(e)[:200])

# 3) stockanalysis adres kalıpları
PAT = ["stocks/aapl", "quote/tyo/7203", "quote/lon/ULVR", "quote/hkg/0700", "quote/sha/600519", "quote/she/000858", "quote/tpe/2330", "quote/nse/RELIANCE",
       "quote/bom/500325", "quote/krx/005930", "quote/tsx/RY", "quote/etr/SAP", "quote/epa/MC", "quote/swx/NESN", "quote/tadawul/2222", "quote/asx/BHP",
       "quote/ams/ASML", "quote/sto/VOLV.B", "quote/bme/ITX", "quote/bvmf/PETR4", "quote/adx/FAB", "quote/bit/ENI", "quote/idx/BBCA", "quote/ebr/KBC",
       "quote/sgx/D05", "quote/cph/NOVO.B", "quote/bmv/WALMEX", "quote/bkk/PTT", "quote/tlv/TEVA", "quote/jse/NPN", "quote/osl/EQNR", "quote/klse/1155"]
def page(path):
    return requests.get("https://stockanalysis.com/" + path + "/financials/ratios/", headers={"user-agent": HEADERS["user-agent"]}, timeout=60)
def roe_row(text):
    for row in re.findall(r"<tr.*?</tr>", text, flags=re.S):
        c = cells(row)
        if c and c[0].startswith("Return on Equity"):
            return c[1:7]
    return None
for p in PAT:
    try:
        t0 = time.time(); r = page(p)
        say("sa", p, r.status_code, len(r.text), "ROE:", roe_row(r.text) if r.status_code == 200 else None, f"{time.time() - t0:.1f}s")
    except Exception as e:
        say("sa", p, "HATA", repr(e)[:120])
    time.sleep(0.8)

# 4) hız sınırı: 60 BIST sayfası art arda (0,5 sn arayla)
codes = [x["name"] for x in json.load(open(os.path.join(OUT, "turkey_scan.json"))) if x.get("price_earnings_ttm")][:60]
st = collections.Counter(); t0 = time.time(); none = 0
for c in codes:
    try:
        r = page("quote/ist/" + c); st[r.status_code] += 1
        if r.status_code == 200 and not roe_row(r.text): none += 1
    except Exception as e:
        st[type(e).__name__] += 1
    time.sleep(0.5)
say("hız: 60 sayfa", dict(st), "ROE satırı olmayan", none, f"toplam {time.time() - t0:.0f} sn")

# 5) aday sayıları: büyük borsalarda 1. sur + son 12 ay kârlılık testi kaç şirket bırakıyor
def scan(market, cols):
    q = {"markets": [market], "columns": cols, "range": [0, 20000], "ignore_unknown_fields": True,
         "filter": [{"left": "is_primary", "operation": "equal", "right": True}, {"left": "type", "operation": "equal", "right": "stock"}, {"left": "typespecs", "operation": "has", "right": ["common"]}]}
    r = requests.post(f"https://scanner.tradingview.com/{market}/scan", headers=HEADERS, json=q, timeout=90)
    j = r.json(); return j["totalCount"], [dict(zip(cols, x["d"])) for x in j["data"]]
COLS = ["name", "exchange", "currency", "fundamental_currency_code", "market_cap_basic", "price_earnings_ttm", "price_book_fq", "industry", "sector", "fiscal_period_current", "net_income_fy_h", "free_cash_flow_fy_h", "net_debt", "ebitda"]
fxr = requests.post("https://scanner.tradingview.com/forex/scan", headers=HEADERS, timeout=60, json={"symbols": {"tickers": ["FX_IDC:USDJPY", "FX_IDC:USDCNY", "FX_IDC:USDINR", "FX_IDC:USDGBP", "FX_IDC:USDTWD", "FX_IDC:USDKRW", "FX_IDC:USDCAD", "FX_IDC:USDEUR", "FX_IDC:USDHKD", "FX_IDC:USDTRY"]}, "columns": ["close"]}).json()
FX = {x["s"][-3:]: x["d"][0] for x in fxr["data"]}; FX["USD"] = 1.0; FX["GBX"] = FX.get("GBP", 0.75) * 100
say("döviz", FX)
for market, infl in (("america", 3.7), ("japan", 2.1), ("china", 0.5), ("india", 4.0), ("uk", 3.0), ("taiwan", 2.0), ("korea", 2.0), ("canada", 2.0), ("germany", 2.2), ("hongkong", 2.0), ("turkey", 29.77)):
    try:
        total, rows = scan(market, COLS)
        ex = collections.Counter(x["exchange"] for x in rows); cu = collections.Counter(x["currency"] for x in rows); fc = collections.Counter(x["fundamental_currency_code"] for x in rows)
        veh = {"Real Estate Investment Trusts", "Investment Trusts/Mutual Funds"}
        s1 = [x for x in rows if x["exchange"] != "OTC" and x["industry"] not in veh and (x["price_earnings_ttm"] or 0) > 0 and (x["price_book_fq"] or 0) > 0
              and (x["market_cap_basic"] or 0) / FX.get(x["currency"], 1e9) >= 6e7]
        def rr(x): return ((1 + x["price_book_fq"] / x["price_earnings_ttm"]) / (1 + infl / 100) - 1) * 100
        c2 = [x for x in s1 if rr(x) >= 12]
        noloss = [x for x in c2 if x["net_income_fy_h"] and len(x["net_income_fy_h"]) >= 5 and all(v is not None and v > 0 for v in x["net_income_fy_h"][:5])]
        say(f"{market}: toplam {total} | borsalar {dict(ex.most_common(6))} | para {dict(cu.most_common(4))} | temel veri parası {dict(fc.most_common(3))} | 1. sur {len(s1)} | aday (reel ROE≥12) {len(c2)} | beş yıl zararsız {len(noloss)} | dönem {dict(collections.Counter(x['fiscal_period_current'] for x in rows).most_common(4))}")
    except Exception as e:
        say(market, "HATA", repr(e)[:200])

open(os.path.join(OUT, "lab2.txt"), "w").write("\n".join(log) + "\n")
