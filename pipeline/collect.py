#!/usr/bin/env python3
"""Castle veri toplayıcı. GitHub'ın makinesinde çalışır (.github/workflows/collect.yml) ve veriyi data/<CC>/in/ altına bırakır.

  python3 pipeline/collect.py run --new 2      # sırada bekleyen ilk iki ülke (henüz taranmamış)
  python3 pipeline/collect.py run --refresh    # taranmış bütün ülkeler (haftalık yenileme)
  python3 pipeline/collect.py run TR US        # adı verilen ülkeler
  python3 pipeline/collect.py probe turkey     # tarayıcıda hangi alan dolu geliyor

Kaynaklar
  evren   : TradingView tarayıcısı (bütün ülkeler). Türkiye için İş Yatırım'ın temel değerler tablosu (bilançoyu daha erken işler).
  beş yıl : stockanalysis.com oran sayfaları; yalnız adaylar için. Bilanço dönemi değişmedikçe sayfa yeniden indirilmez.
  makro   : döviz ve son yıllık enflasyon TradingView; yıl sonu enflasyonu IMF WEO (DBnomics üzerinden), yedek Dünya Bankası.

Bu betik hiçbir şirketi elemez ve hiçbir şeyi yayımlamaz. Gelen veri `python3 pipeline/accept.py <CC>` ile denetlenip yerine alınır.
Gereken: `pip install requests` ve bu adreslere erişim (Claude oturumlarında kapalıdır; o yüzden GitHub'da çalışır).
"""
import collections, datetime, html, json, os, random, re, statistics, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
TV = "https://scanner.tradingview.com/{market}/scan"
HEADERS = {
    "accept": "text/plain, */*; q=0.01",
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "origin": "https://www.tradingview.com",
    "referer": "https://www.tradingview.com/",
}
UA = {"user-agent": HEADERS["user-agent"], "accept-language": "tr-TR,tr;q=0.9,en;q=0.8"}
# evren için istenen alanlar
COLUMNS = [
    "name", "description", "exchange", "sector", "industry", "currency", "fundamental_currency_code",
    "close", "market_cap_basic", "price_earnings_ttm", "price_book_fq", "float_shares_percent_current", "total_shares_outstanding",
    "fiscal_period_current", "fiscal_period_end_current",
    # F/K boş geldiğinde nedenini ayırmak için (zarar mı, kaynakta veri mi yok): son 12 ay hisse başına kâr ve özsermaye kârlılığı
    "earnings_per_share_diluted_ttm", "earnings_per_share_basic_ttm", "return_on_equity", "net_income",
]
# probe komutu için: geçmiş dizileri dahil geniş liste
PROBE = COLUMNS + ["country", "type", "typespecs", "return_on_equity", "return_on_equity_fy", "net_income_fy", "total_equity_fq", "net_debt", "ebitda",
                   "free_cash_flow", "dividends_yield_current", "net_income_fy_h", "free_cash_flow_fy_h", "total_debt_fy_h", "ebitda_fy_h", "total_assets_fy_h", "fiscal_period_fy_h"]
FILTER = [{"left": "is_primary", "operation": "equal", "right": True}, {"left": "type", "operation": "equal", "right": "stock"},
          {"left": "typespecs", "operation": "has", "right": ["common"]}]
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
# borç ve nakit testinin anlamlı olmadığı işler (banka, sigorta, aracı kurum, finansman, holding)
FIN_INDUSTRIES = {"Major Banks", "Regional Banks", "Savings Banks", "Finance/Rental/Leasing", "Investment Banks/Brokers", "Investment Managers",
                  "Financial Conglomerates", "Life/Health Insurance", "Multi-Line Insurance", "Property/Casualty Insurance", "Specialty Insurance",
                  "Insurance Brokers/Services"}
EXCLUDE_EXCHANGES = {"OTC"}        # tezgâh üstü: borsa değil
MINOR = {"GBX": ("GBP", 100.0), "GBp": ("GBP", 100.0), "ZAC": ("ZAR", 100.0), "ZAc": ("ZAR", 100.0), "ILA": ("ILS", 100.0), "KWF": ("KWD", 1000.0)}
ISO3 = dict(US="USA", CN="CHN", JP="JPN", TW="TWN", IN="IND", GB="GBR", KR="KOR", CA="CAN", FR="FRA", DE="DEU", CH="CHE", SA="SAU", AU="AUS", NL="NLD",
            SE="SWE", ES="ESP", BR="BRA", AE="ARE", HK="HKG", IT="ITA", ID="IDN", BE="BEL", SG="SGP", DK="DNK", MX="MEX", RU="RUS", TH="THA", IL="ISR",
            ZA="ZAF", NO="NOR", MY="MYS", FI="FIN", PH="PHL", VN="VNM", CL="CHL", IE="IRL", PL="POL", QA="QAT", TR="TUR", AT="AUT", GR="GRC", KW="KWT",
            CO="COL", RO="ROU", MA="MAR", AR="ARG", PT="PRT", NZ="NZL", NG="NGA", PE="PER", HU="HUN", EG="EGY", PK="PAK", BD="BGD", CZ="CZE", LU="LUX",
            CY="CYP", HR="HRV", KE="KEN", SI="SVN", IS="ISL", BH="BHR", LK="LKA", TN="TUN", LT="LTU", EE="EST", BG="BGR", RS="SRB", SK="SVK", LV="LVA", VE="VEN")
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load(path, default=None):
    if not os.path.exists(path):
        return default
    return json.load(open(path, encoding="utf-8"))


def dump(obj, path, indent=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=indent, separators=None if indent is not None else (",", ":"))


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def stamp():
    return now().strftime("%Y-%m-%dT%H:%M:%SZ")


def cells(row):
    return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, flags=re.S)]


def real(roe, cpi):
    return None if roe is None or cpi is None else ((1 + roe / 100.0) / (1 + cpi / 100.0) - 1) * 100.0


def nice(x):
    """Yuvarlak sayı: 1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8 x 10^k içinden en yakını."""
    if not x or x <= 0:
        return x
    k = 10 ** int(__import__("math").floor(__import__("math").log10(x)))
    best = min((1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10), key=lambda m: abs(m * k - x))
    v = best * k
    return int(v) if v >= 10 else round(v, 2)


# ---------------------------------------------------------------- TradingView
def tv_post(url, body):
    import requests
    last = None
    for attempt in range(4):
        r = requests.post(url, json=body, headers=HEADERS, timeout=90)
        if r.status_code == 200:
            return r.json()
        last = f"{r.status_code}: {r.text[:300]}"
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * (attempt + 1)); continue
        break
    raise RuntimeError("TradingView " + str(last))


def tv_scan(market, columns):
    j = tv_post(TV.format(market=market), {"markets": [market], "symbols": {}, "options": {"lang": "en"}, "columns": columns, "filter": FILTER,
                                           "sort": {"sortBy": "market_cap_basic", "sortOrder": "desc"}, "range": [0, 20000], "ignore_unknown_fields": True})
    return j["totalCount"], [dict(zip(["ticker"] + columns, [row["s"]] + row["d"])) for row in j["data"]]


def tv_quotes(tickers, where="global"):
    """Tek tek sembollerin son değeri (döviz kurları, enflasyon göstergeleri)."""
    if not tickers:
        return {}
    j = tv_post(TV.format(market=where), {"symbols": {"tickers": tickers}, "columns": ["close"], "ignore_unknown_fields": True})
    return {row["s"]: row["d"][0] for row in j.get("data", []) if row["d"][0] is not None}


def fx_rates(curs):
    """1 ABD doları kaç birim? {'TRY': 50.2, ...}"""
    want = sorted(set(c for c in curs if c and c != "USD"))
    q = tv_quotes(["FX_IDC:USD" + c for c in want], "forex")
    out = {"USD": 1.0}
    for c in want:
        if "FX_IDC:USD" + c in q:
            out[c] = q["FX_IDC:USD" + c]
    return out


def _median(xs):
    xs = sorted(xs)
    return None if not xs else (xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2)


def pe_checks(rows):
    """F/K'sı dolu şirketlerde aynı kaynağın öbür alanları F/K ile tutuyor mu? Tutmuyorsa o yol kullanılmaz.
    Döner: (hisse başına kâr yolu kullanılabilir mi, özsermaye kârlılığı ölçeği ya da None, özet)."""
    e_r, r_r = [], []
    for r in rows:
        pe, pb, close, cur = r.get("price_earnings_ttm"), r.get("price_book_fq"), r.get("close"), r.get("currency")
        if not pe or pe <= 0 or not close:
            continue
        eps = r.get("earnings_per_share_diluted_ttm")
        pmaj, pdiv = MINOR.get(cur, (cur, 1.0))
        if eps and eps > 0 and r.get("fundamental_currency_code") == pmaj:
            e_r.append(close / pdiv / eps / pe)
        roe = r.get("return_on_equity")
        if roe and roe > 0 and pb and pb > 0:
            r_r.append(roe / (pb / pe * 100.0))
    em, rm = _median(e_r), _median(r_r)
    eps_ok = bool(em and len(e_r) >= 30 and 0.95 < em < 1.05)
    scale = None
    if rm and len(r_r) >= 30:
        scale = 1.0 if 0.6 < rm < 1.6 else 100.0 if 0.006 < rm < 0.016 else None
    near = lambda xs, m, tol: None if not xs or not m else round(100 * sum(1 for x in xs if abs(x / m - 1) <= tol) / len(xs), 1)
    return eps_ok, scale, dict(eps_n=len(e_r), eps_med=None if em is None else round(em, 4), eps_within5=near(e_r, em, 0.05),
                               roe_n=len(r_r), roe_med=None if rm is None else round(rm, 4), roe_within25=near(r_r, rm, 0.25), roe_scale=scale, eps_ok=eps_ok)


def pe_fallback(r, close, pb, cur, eps_ok, roe_scale):
    """Kaynağın F/K alanı boşsa nedenini aynı kaynağın son 12 ay alanlarından ayırır.
    Döner: (F/K ya da None, nasıl bulundu: "eps" | "roe" | None, boşsa neden: "loss" | "nodata" | None).
    Kâr varsa F/K aynı büyüklükten hesaplanır: fiyat ÷ hisse başına kâr (para birimi aynıysa), yoksa PD/DD ÷ özsermaye kârlılığı."""
    eps = r.get("earnings_per_share_diluted_ttm")
    if eps is None:
        eps = r.get("earnings_per_share_basic_ttm")
    roe = r.get("return_on_equity")
    if (eps is not None and eps <= 0) or (eps is None and roe is not None and roe <= 0):
        return None, None, "loss"
    pmaj, pdiv = MINOR.get(cur, (cur, 1.0))
    if eps_ok and eps is not None and eps > 0 and close and r.get("fundamental_currency_code") == pmaj:
        pe = close / pdiv / eps
        if 0.2 < pe < 5000:
            return pe, "eps", None
    if roe_scale and roe is not None and roe > 0 and pb and pb > 0:
        pe = pb / (roe * roe_scale / 100.0)
        if 0.2 < pe < 5000:
            return pe, "roe", None
    return None, None, "nodata"


def universe_tv(k, st):
    total, rows = tv_scan(k["market"], COLUMNS)
    eps_ok, roe_scale, pe_chk = pe_checks(rows)
    fix = collections.Counter()
    mode = lambda key: (collections.Counter(r[key] for r in rows if r.get(key)).most_common(1) or [(None, 0)])[0][0]
    main, pcur = mode("fundamental_currency_code"), mode("currency")
    majors = set(MINOR.get(r["currency"], (r["currency"],))[0] for r in rows if r.get("currency")) | {main}
    fx = fx_rates(majors)
    excl, chk, out, seen = collections.Counter(), collections.Counter(), [], {}
    skip = set(k.get("exclude_exchanges", [])) | EXCLUDE_EXCHANGES
    for r in rows:
        if r.get("exchange") in skip:
            excl[r["exchange"]] += 1; continue
        close, mc = r.get("close"), r.get("market_cap_basic")
        if close is None or mc is None:
            excl["fiyat ya da piyasa değeri yok"] += 1; continue
        cur = r.get("currency") or pcur
        mcur, div = MINOR.get(cur, (cur, 1.0))            # piyasa değeri ana birimde gelir (pens değil sterlin)
        sh = r.get("total_shares_outstanding")
        if sh and mc:
            ratio = close * sh / mc
            chk["tutarlı" if 0.7 < ratio / div < 1.4 else "alt birim ayrımı beklenenden farklı" if 0.7 < ratio < 1.4 and div != 1 else "pay sayısıyla tutmuyor"] += 1
            if 0.7 < ratio < 1.4 and div != 1:
                mcur = cur
        else:
            chk["pay sayısı yok"] += 1
        if mcur != main:
            if mcur in fx and main in fx:
                mc = mc / fx[mcur] * fx[main]
            else:
                excl["kur bulunamadı: " + str(mcur)] += 1; continue
        pb, pe, fl = r.get("price_book_fq"), r.get("price_earnings_ttm"), r.get("float_shares_percent_current")
        pes = why_none = None
        if pe is None or pe <= 0:                          # kaynak F/K vermedi: zarar mı, veri mi eksik?
            pe, pes, why_none = pe_fallback(r, close, pb, cur, eps_ok, roe_scale)
            fix[pes or why_none] += 1
        c = r["name"]
        if c in seen:                                      # aynı kod iki borsada: ikincisine borsa eki
            c = c + ":" + str(r.get("exchange"))
        seen[c] = 1
        u = dict(c=c, n=r.get("description") or r["name"], s=SECTOR_TR.get(r.get("sector"), r.get("sector") or "Diğer"), ind=r.get("industry"),
                 p=close, m=round(mc / 1e6, 1), f=None if fl is None else round(fl, 1),
                 pe=None if pe is None else round(pe, 2), pb=None if pb is None else round(pb, 3), per=r.get("fiscal_period_current"),
                 nom=0, fin=1 if r.get("industry") in FIN_INDUSTRIES else 0, veh=1 if r.get("industry") in VEHICLE_INDUSTRIES else 0, x=r.get("exchange"))
        if cur != pcur:
            u["pc"] = cur
        if pes:
            u["pes"] = pes                                 # F/K kaynağın F/K alanından değil, aynı kaynağın başka alanından hesaplandı
        if why_none:
            u["np"] = why_none                             # F/K yok: "loss" zarar, "nodata" kaynakta son 12 ay kârı yok
        out.append(u)
    st.update(source="TradingView tarayıcısı", market=k["market"], total=total, kept=len(out), excluded=dict(excl), mcap_check=dict(chk),
              cur=main, pcur=pcur, exchanges=dict(collections.Counter(u["x"] for u in out).most_common()),
              periods=dict(collections.Counter(str(u["per"]) for u in out).most_common(6)))
    big = sorted(out, key=lambda u: -u["m"])
    st["pe_fix"] = dict(pe_chk, counts=dict(fix),
                        nodata_top=[u["c"] for u in big if u.get("np") == "nodata"][:15],
                        fixed_top=[[u["c"], u["pe"], u["pes"]] for u in big if u.get("pes")][:15])
    return out, fx.get(main)


# ---------------------------------------------------------------- İş Yatırım (Türkiye)
IY = "https://www.isyatirim.com.tr/tr-tr/analiz/hisse/Sayfalar/Temel-Degerler-Ve-Oranlar.aspx"


def trnum(s):
    s = s.strip()
    if s in ("A/D", "", "-"):
        return None
    return float(s.replace(".", "").replace(",", "."))


def universe_iy(k, meta, st):
    import requests
    r = requests.get(IY, headers=UA, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"İş Yatırım {r.status_code}")
    oz, ra, asof = {}, {}, None
    for attr, body in re.findall(r"<table(.*?)>(.*?)</table>", r.text, flags=re.S):
        rows = re.findall(r"<tr.*?</tr>", body, flags=re.S)
        if not rows:
            continue
        head = cells(rows[0])
        if head[:3] == ["Kod", "Hisse Adı", "Sektör"] and len(head) >= 7:
            for row in rows[1:]:
                c = cells(row)
                if len(c) >= 7 and c[0]:
                    oz[c[0]] = dict(n=c[1], s=c[2].replace("Perakande", "Perakende"), p=trnum(c[3]), m=trnum(c[4]), musd=trnum(c[5]), f=trnum(c[6]))
        elif head[:3] == ["Kod", "Kapanış (TL)", "F/K"] and "Son Dönem" in head:
            ip = head.index("PD/DD"); il = head.index("Son Dönem")
            for row in rows[1:]:
                c = cells(row)
                if len(c) > il and c[0]:
                    ra[c[0]] = dict(p=trnum(c[1]), pe=trnum(c[2]), pb=trnum(c[ip]), per=c[il] or None)
        elif asof is None:
            m = re.search(r"(\d{1,2}) (" + "|".join(AYLAR) + r") (20\d\d)", " ".join(head))
            if m:
                asof = f"{m.group(3)}-{AYLAR.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"
    if len(oz) < 300 or len(ra) < 300:
        raise RuntimeError(f"İş Yatırım tabloları okunamadı (özet {len(oz)}, oranlar {len(ra)})")
    fl = meta.get("flags", {}) if meta else {}
    veh, fin, nom, nomc = set(fl.get("veh", [])), set(fl.get("fin", [])), set(fl.get("nom", [])), set(fl.get("nom_codes", []))
    out, miss = [], []
    for c in sorted(oz):
        o, q = oz[c], ra.get(c)
        if q is None or o["p"] is None or o["m"] is None:
            miss.append(c); continue
        out.append(dict(c=c, n=o["n"], s=o["s"], p=o["p"], m=o["m"], f=o["f"], pe=q["pe"], pb=q["pb"], per=q["per"],
                        nom=1 if (o["s"] in nom or c in nomc) else 0, fin=1 if o["s"] in fin else 0, veh=1 if o["s"] in veh else 0, x="BIST"))
    fxs = [o["m"] / o["musd"] for o in oz.values() if o["m"] and o["musd"] and o["musd"] > 50]
    st.update(source="İş Yatırım: temel değerler ve oranlar", market=k["market"], total=len(oz), kept=len(out), excluded={"oran satırı yok": len(miss)} if miss else {},
              cur="TRY", pcur="TRY", price_date=asof, periods=dict(collections.Counter(str(u["per"]) for u in out).most_common(6)),
              implied_fx=round(statistics.median(fxs), 3) if fxs else None)
    return out, None


# ---------------------------------------------------------------- makro: döviz, enflasyon
def weo_vintages():
    y, m = now().year, now().month
    out = []
    for yy in (y, y - 1, y - 2):
        for mm in (10, 4):
            if (yy, mm) <= (y, m):
                out.append(f"{yy}-{mm:02d}")
    return out + ["latest"]


def cpi_years(cc, years):
    """Yıl sonu yıllık tüketici enflasyonu (%). Önce IMF WEO (dönem sonu), olmazsa Dünya Bankası (yıllık ortalama)."""
    import requests
    iso3, out, src, errs = ISO3.get(cc), {}, {}, []
    for v in weo_vintages():
        try:
            r = requests.get(f"https://api.db.nomics.world/v22/series/IMF/WEO:{v}/{iso3}.PCPIEPCH.pcent_change?observations=1", headers=UA, timeout=60)
            if r.status_code != 200:
                continue
            docs = r.json().get("series", {}).get("docs", [])
            if not docs:
                continue
            d = docs[0]; vint = (d.get("dataset_code") or "").replace("WEO:", "")
            vy = int(vint[:4]) if vint[:4].isdigit() else now().year
            obs = dict(zip(d.get("period", []), d.get("value", [])))
            for y in years:
                # sürümün yılından önceki yıllar gerçekleşmedir; aynı ve sonraki yıllar tahmindir, kullanılmaz
                if y not in out and int(y) < vy and isinstance(obs.get(y), (int, float)):
                    out[y] = round(obs[y], 2); src[y] = "IMF WEO " + vint + " (dönem sonu)"
            if all(y in out for y in years):
                break
        except Exception as e:
            errs.append(f"IMF WEO {v}: {type(e).__name__}")
            continue
    if not all(y in out for y in years):
        for attempt in range(2):
            try:
                r = requests.get(f"https://api.worldbank.org/v2/country/{iso3}/indicator/FP.CPI.TOTL.ZG?format=json&date={years[0]}:{years[-1]}&per_page=50", headers=UA, timeout=90)
                j = r.json()
                for o in ((j[1] if isinstance(j, list) and len(j) > 1 else None) or []):
                    if o["date"] in years and o["date"] not in out and o["value"] is not None:
                        out[o["date"]] = round(o["value"], 2); src[o["date"]] = "Dünya Bankası FP.CPI.TOTL.ZG (yıllık ortalama)"
                break
            except Exception as e:
                errs.append(f"Dünya Bankası: {type(e).__name__} {str(e)[:80]}")
                time.sleep(3)
    return out, src, errs


def macro(cc, k, st, fx_main, years):
    cur = st.get("cur")
    out = dict(fetched=stamp(), cur=cur, pcur=st.get("pcur"), years=years)
    try:
        if fx_main is None and cur:
            fx_main = fx_rates([cur]).get(cur)
        out["fx"] = None if fx_main is None else round(fx_main, 4)
        if fx_main:
            out["mcapMin"] = nice(60e6 * fx_main / 1e6)       # yaklaşık 60 milyon ABD doları, milyon yerel para
    except Exception as e:
        st["errors"].append("döviz: " + repr(e)[:160])
    try:
        q = tv_quotes(["ECONOMICS:" + cc + "IRYY"])
        out["cpi_cur"] = q.get("ECONOMICS:" + cc + "IRYY")
        out["cpi_cur_src"] = "TradingView ECONOMICS:" + cc + "IRYY (son açıklanan yıllık TÜFE)"
    except Exception as e:
        st["errors"].append("enflasyon (son): " + repr(e)[:160])
    try:
        out["cpi"], out["cpi_src"], errs = cpi_years(cc, years)
        miss = [y for y in years if y not in out["cpi"]]
        if miss:
            out["cpi_missing"] = miss      # bu yılları ülkenin istatistik kurumundan tamamla (CLAUDE.md, İş A)
        if errs:
            out["cpi_errors"] = errs
    except Exception as e:
        st["errors"].append("enflasyon (yıllar): " + repr(e)[:160])
    return out


# ---------------------------------------------------------------- beş yıllık oranlar: stockanalysis
def sa_paths(u, k, src):
    t = u["c"].split(":")[0]
    pats = (k.get("sa") or {}).get(u.get("x") or "") or src.get("sa", {}).get(u.get("x") or "")
    if not pats:
        return []
    if isinstance(pats, str):
        pats = [pats]
    v = dict(t=t, lc=t.lower(), t4=t.zfill(4), t5=t.zfill(5), t6=t.zfill(6), dot=t.replace("_", "."), dash=t.replace("_", "-").replace(".", "-"),
             lcdot=t.lower().replace("_", "."), lcdash=t.lower().replace("_", ".").replace("/", "."))
    return [p.format(**v) for p in pats]


def pnum(s):
    s = (s or "").strip().replace(",", "").replace("%", "")
    if s in ("", "-", "n/a", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def sa_parse(text):
    rows = {}
    for row in re.findall(r"<tr.*?</tr>", text, flags=re.S):
        c = cells(row)
        if len(c) >= 2 and c[0] not in rows:
            rows[c[0]] = c[1:]
    head = rows.get("Fiscal Year")
    if not head:
        return None
    has_cur = head[0] in ("Current", "TTM")
    fy = [h.replace("FY", "").strip() for h in head[1 if has_cur else 0:]][:5]

    def series(*names):
        for nm in names:
            for key, v in rows.items():
                if key.startswith(nm):
                    cur = pnum(v[0]) if has_cur else None
                    vals = [pnum(x) for x in v[1 if has_cur else 0:]][:5]
                    vals = vals + [None] * (len(fy) - len(vals))
                    return [None] * (5 - len(vals)) + vals[::-1] + [cur]      # eskiden yeniye beş mali yıl, sonra güncel
        return [None] * 6

    roe = series("Return on Equity")
    m = re.search(r'lastUpdated:"(\d{4}-\d{2}-\d{2})"', text)
    t = re.search(r'lastTrailingDate:"([A-Z][a-z]{2}) (\d{1,2}), (\d{4})"', text)
    out = dict(asof=m.group(1) if m else None, stale=0, fy=[None] * (5 - len(fy)) + fy[::-1],
               roe=roe, roic=series("Return on Invested Capital", "Return on Capital (ROIC)"), fcf=series("FCF Yield"),
               nd=series("Net Debt / EBITDA")[-1], pe=series("PE Ratio")[-1], pb=series("PB Ratio")[-1], dy=series("Dividend Yield")[-1], po=series("Payout Ratio")[-1])
    if t and t.group(1) in MON:
        out["ttm"] = f"{t.group(3)}-{MON.index(t.group(1)) + 1:02d}-{int(t.group(2)):02d}"
    if out["asof"]:
        age = (now().date() - datetime.date.fromisoformat(out["asof"])).days
        out["stale"] = 1 if age > 365 else 0
    return out


def candidates(uni, meta, mac, P):
    cpi_cur = (meta or {}).get("cpi", {}).get("cur", mac.get("cpi_cur"))
    mcap_min = (meta or {}).get("mcapMin", mac.get("mcapMin")) or 0
    deflate_all = (meta or {}).get("deflate", "all") == "all"
    out = []
    for u in uni:
        pe, pb = u.get("pe"), u.get("pb")
        if u.get("veh") or not pe or pe <= 0 or not pb or pb <= 0 or u["m"] < mcap_min:
            continue
        roe = pb / pe * 100.0
        rr = real(roe, cpi_cur or 0.0) if (deflate_all or u.get("nom")) else roe
        if rr >= P["roeMin"] - 1.0:                        # bir puan pay: eşikteki şirketin verisi de hazır olsun
            out.append(u)
    return out


def history(cc, k, uni, meta, mac, st, budget):
    import requests
    P, src = load(J("pipeline", "params.json")), load(J("pipeline", "sources.json"), {})
    live, old = load(J("data", cc, "history.json"), {}), load(J("data", cc, "in", "history.json"), {})
    cand = candidates(uni, meta, mac, P)
    cand.sort(key=lambda u: -u["m"])
    out, got, fail, nomap, kept, blocked, streak = {}, 0, [], 0, 0, False, 0
    today = now().date()
    for u in cand:
        c = u["c"]
        prev = old.get(c) or live.get(c)
        fresh = prev and prev.get("per") == u.get("per") and prev.get("got") and (today - datetime.date.fromisoformat(prev["got"])).days <= 45
        if fresh or blocked or got >= budget:
            if prev:
                out[c] = prev; kept += 1
            continue
        paths = sa_paths(u, k, src)
        if not paths:
            nomap += 1
            if prev:
                out[c] = prev
            continue
        ent, code = None, None
        for p in paths:
            url = "https://stockanalysis.com/" + p + "/financials/ratios/"
            for attempt in range(3):
                try:
                    r = requests.get(url, headers={"user-agent": HEADERS["user-agent"]}, timeout=60)
                    code = r.status_code
                except Exception as e:
                    code = type(e).__name__
                if code in (429, 500, 502, 503, 504) or isinstance(code, str):
                    time.sleep(8 * (attempt + 1)); continue
                break
            time.sleep(0.45 + random.random() * 0.3)
            if code == 200:
                ent = sa_parse(r.text)
                if ent:
                    ent.update(per=u.get("per"), got=today.isoformat(), url=url)
                    break
        if ent:
            out[c] = ent; got += 1; streak = 0
        else:
            fail.append([c, code]); streak += 1
            if prev:
                out[c] = prev
            if code in (403, 429) and streak >= 8:         # engellendik: ısrar etme, kalanlar sonraki çalıştırmaya
                blocked = True
    st["history"] = dict(candidates=len(cand), have=len(out), fetched=got, kept=kept, no_mapping=nomap, failed=fail[:60], failed_n=len(fail), blocked=blocked,
                         budget_left=budget - got)
    return out, got


# ---------------------------------------------------------------- çalıştırma
def countries():
    return load(J("pipeline", "countries.json"))["countries"]


def run_one(cc, budget):
    k = next((x for x in countries() if x["cc"] == cc), None)
    if not k:
        raise SystemExit("bilinmeyen ülke: " + cc)
    meta = load(J("data", cc, "meta.json"))
    st = dict(cc=cc, fetched=stamp(), errors=[])
    d = J("data", cc, "in")
    y = now().year
    years = (meta or {}).get("years") or [str(v) for v in range(y - 5, y)]
    got = 0
    try:
        if (meta or {}).get("source") == "isyatirim" or k.get("source") == "isyatirim":
            uni, fx_main = universe_iy(k, meta, st)
        else:
            uni, fx_main = universe_tv(k, st)
        st["pe_filled_pct"] = round(100 * sum(1 for u in uni if u.get("pe")) / max(1, len(uni)), 1)
        st["top5"] = [dict(c=u["c"], n=u["n"], p=u["p"], m=u["m"], pe=u["pe"], pb=u["pb"], per=u["per"]) for u in sorted(uni, key=lambda u: -u["m"])[:5]]
        dump(uni, os.path.join(d, "universe.json"), indent=0)
        mac = macro(cc, k, st, fx_main, years)
        dump(mac, os.path.join(d, "macro.json"), indent=1)
        hist, got = history(cc, k, uni, meta, mac, st, budget)
        dump(hist, os.path.join(d, "history.json"), indent=0)
        st["ok"] = True
    except Exception as e:
        st["ok"] = False; st["errors"].append(repr(e)[:400])
    dump(st, os.path.join(d, "status.json"), indent=1)
    h = st.get("history", {})
    print(f"{cc}: {'tamam' if st['ok'] else 'HATA'} | şirket {st.get('kept')} | F/K dolu %{st.get('pe_filled_pct')} | aday {h.get('candidates')} | indirilen sayfa {h.get('fetched')} "
          f"| eksik {h.get('failed_n')} | hata {st['errors']}")
    return st, got


def plan(args):
    cs, done = countries(), lambda cc: os.path.exists(J("data", cc, "core.json"))
    if "--refresh" in args:
        return [k["cc"] for k in cs if done(k["cc"])]
    if "--new" in args:
        i = args.index("--new"); n = int(args[i + 1]) if len(args) > i + 1 and args[i + 1].isdigit() else 2
        return [k["cc"] for k in cs if not k.get("hold") and not done(k["cc"])][:n]
    return [a.upper() for a in args if not a.startswith("--") and not a.isdigit()]


def run(args):
    ccs, budget, res = plan(args), 6000, []
    print("toplanacak:", ", ".join(ccs) or "-")
    for cc in ccs:
        st, got = run_one(cc, budget)
        budget -= got
        h = st.get("history", {})
        res.append(dict(cc=cc, ok=st["ok"], fetched=st["fetched"], n=st.get("kept"), candidates=h.get("candidates"), pages=h.get("fetched"), missing=h.get("failed_n"),
                        blocked=h.get("blocked"), errors=st["errors"]))
    dump(dict(when=stamp(), args=args, results=res), J("data", "_collect.json"), indent=1)


def probe(market):
    total, rows = tv_scan(market, PROBE)
    print(f"{market}: toplam {total}, gelen {len(rows)}")
    for c in PROBE:
        filled = sum(1 for r in rows if r.get(c) not in (None, "", []))
        ex = next((r[c] for r in rows if r.get(c) not in (None, "", [])), None)
        print(f"  {c:38} dolu %{100 * filled / max(1, len(rows)):5.1f}   örnek: {str(ex)[:70]}")


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("run", "probe"):
        raise SystemExit(__doc__)
    if sys.argv[1] == "probe":
        probe(sys.argv[2])
    else:
        run(sys.argv[2:])
