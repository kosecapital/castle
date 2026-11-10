#!/usr/bin/env python3
"""Castle veri toplayıcı: bir ülkenin bütün hisselerini TradingView tarayıcısından çeker.

Kullanım:
  python3 pipeline/collect.py probe turkey          # hangi alan dolu geliyor? (yeni ülkede ve ilk çalıştırmada önce bunu çalıştır)
  python3 pipeline/collect.py universe TR           # data/TR/raw/scan.json ve data/TR/universe.json yazar (meta.json gerekir)

Gereken: `pip install requests` ve çalışma ortamının scanner.tradingview.com adresine erişimi.
Bu betik yalnızca veri indirir ve normalleştirir; hiçbir şirketi elemez (onu funnel.py yapar).

ÖNEMLİ: Bu toplayıcı ilk yazıldığında canlı sınanamadı (ortamın ağ izni yoktu). İlk çalıştırmada
CLAUDE.md'deki "Toplayıcıyı doğrula" adımlarını uygula; alan adları ya da birimler beklenenden farklıysa
betiği düzelt ve düzeltmeyi commit et.
"""
import json, os, sys, time, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://scanner.tradingview.com/{market}/scan"
HEADERS = {
    "accept": "text/plain, */*; q=0.01",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "origin": "https://www.tradingview.com",
    "referer": "https://www.tradingview.com/",
}
# istenen alanlar; bilinmeyen alan boş döner (ignore_unknown_fields)
COLUMNS = [
    "name", "description", "exchange", "type", "typespecs", "sector", "industry", "country", "currency", "fundamental_currency_code",
    "close", "market_cap_basic", "price_earnings_ttm", "price_book_fq", "price_book_ratio",
    "return_on_equity", "return_on_equity_fy", "return_on_invested_capital", "return_on_invested_capital_fy",
    "net_income", "net_income_fy", "total_equity_fq", "total_equity_fy",
    "net_debt", "total_debt", "ebitda", "free_cash_flow", "free_cash_flow_fy",
    "float_shares_percent_current", "float_shares_outstanding", "total_shares_outstanding",
    "dividend_yield_recent", "dividends_yield_current", "dividend_payout_ratio_ttm",
    "fiscal_period_current", "fiscal_period_end_current", "earnings_release_date",
    # geçmiş dizileri (varsa): eskiden yeniye mali yıllar
    "net_income_fy_h", "total_equity_fy_h", "free_cash_flow_fy_h", "return_on_equity_fy_h", "return_on_invested_capital_fy_h",
    "total_debt_fy_h", "ebitda_fy_h", "cash_n_short_term_invest_fy_h", "fiscal_period_fy_h", "fiscal_period_end_fy_h",
]
SECTOR_TR = {
    "Commercial Services": "Ticari Hizmetler", "Communications": "İletişim", "Consumer Durables": "Dayanıklı Tüketim",
    "Consumer Non-Durables": "Dayanıksız Tüketim", "Consumer Services": "Tüketici Hizmetleri", "Distribution Services": "Dağıtım",
    "Electronic Technology": "Elektronik Teknoloji", "Energy Minerals": "Enerji Madenleri", "Finance": "Finans",
    "Health Services": "Sağlık Hizmetleri", "Health Technology": "Sağlık Teknolojisi", "Industrial Services": "Sanayi Hizmetleri",
    "Miscellaneous": "Diğer", "Non-Energy Minerals": "Enerji Dışı Madenler", "Process Industries": "Proses Sanayii",
    "Producer Manufacturing": "Üretim Sanayii", "Retail Trade": "Perakende", "Technology Services": "Teknoloji Hizmetleri",
    "Transportation": "Ulaştırma", "Utilities": "Kamu Hizmetleri",
}
VEHICLE_INDUSTRIES = {"Real Estate Investment Trusts", "Investment Trusts/Mutual Funds"}


def scan(market, columns=COLUMNS, limit=20000):
    import requests
    q = {
        "markets": [market], "symbols": {}, "options": {"lang": "en"}, "columns": columns,
        "filter": [{"left": "is_primary", "operation": "equal", "right": True},
                   {"left": "type", "operation": "equal", "right": "stock"},
                   {"left": "typespecs", "operation": "has", "right": ["common"]}],
        "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, "range": [0, limit], "ignore_unknown_fields": True,
    }
    for attempt in range(4):
        r = requests.post(URL.format(market=market), json=q, headers=HEADERS, timeout=60)
        if r.status_code == 200:
            j = r.json()
            return j["totalCount"], [dict(zip(["ticker"] + columns, [row["s"]] + row["d"])) for row in j["data"]]
        if r.status_code in (429, 500, 502, 503):
            time.sleep(5 * (attempt + 1)); continue
        raise SystemExit(f"TradingView {r.status_code}: {r.text[:400]}")
    raise SystemExit("TradingView yanıt vermedi (4 deneme)")


def probe(market):
    total, rows = scan(market)
    print(f"{market}: toplam {total}, gelen {len(rows)}")
    for c in COLUMNS:
        filled = sum(1 for r in rows if r.get(c) not in (None, "", []))
        ex = next((r[c] for r in rows if r.get(c) not in (None, "", [])), None)
        print(f"  {c:38} dolu %{100 * filled / max(1, len(rows)):5.1f}   örnek: {str(ex)[:70]}")
    print("ilk üç satır:"); [print("  ", json.dumps(r, ensure_ascii=False)[:600]) for r in rows[:3]]


def universe(cc):
    d = os.path.join(ROOT, "data", cc)
    meta = json.load(open(os.path.join(d, "meta.json"), encoding="utf-8"))
    total, rows = scan(meta["market"])
    os.makedirs(os.path.join(d, "raw"), exist_ok=True)
    json.dump(dict(fetched=datetime.datetime.utcnow().isoformat() + "Z", market=meta["market"], total=total, rows=rows),
              open(os.path.join(d, "raw", "scan.json"), "w", encoding="utf-8"), ensure_ascii=False)
    nominal_ind = set(meta.get("nominal_industries", []))
    scale = meta.get("mcap_scale", 1e6)      # piyasa değeri milyon yerel para birimi olarak saklanır
    out = []
    for r in rows:
        if r.get("close") is None or r.get("market_cap_basic") is None:
            continue
        pb = r.get("price_book_fq") if r.get("price_book_fq") is not None else r.get("price_book_ratio")
        fl = r.get("float_shares_percent_current")
        if fl is None and r.get("float_shares_outstanding") and r.get("total_shares_outstanding"):
            fl = 100.0 * r["float_shares_outstanding"] / r["total_shares_outstanding"]
        out.append(dict(
            c=r["name"], n=r.get("description") or r["name"], s=SECTOR_TR.get(r.get("sector"), r.get("sector") or "Diğer"), ind=r.get("industry"),
            p=r["close"], m=round(r["market_cap_basic"] / scale, 1), f=None if fl is None else round(fl, 1),
            pe=r.get("price_earnings_ttm"), pb=pb, per=r.get("fiscal_period_current"),
            nom=1 if r.get("industry") in nominal_ind else 0, fin=1 if r.get("sector") == "Finance" else 0,
            veh=1 if r.get("industry") in VEHICLE_INDUSTRIES else 0, x=r.get("exchange"), cur=r.get("currency")))
    json.dump(out, open(os.path.join(d, "universe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"{cc}: {len(out)} şirket yazıldı (tarayıcı toplamı {total}). F/K dolu: {sum(1 for u in out if u['pe'])}, PD/DD dolu: {sum(1 for u in out if u['pb'])}")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("probe", "universe"):
        raise SystemExit(__doc__)
    (probe if sys.argv[1] == "probe" else universe)(sys.argv[2])
