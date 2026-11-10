#!/usr/bin/env python3
"""Castle süzgeci: bir ülkenin normalleştirilmiş verisinden dört surun sonucunu üretir.

Girdi  (data/<CC>/): meta.json, universe.json, history.json, reports.json (olmayabilir)
Çıktı  (data/<CC>/core.json): {cc, asof, U, L2, R}

Kullanım: python3 pipeline/funnel.py TR
Kurallar pipeline/params.json içindedir; ülkeye özgü ayarlar meta.json içindedir.
Bu betik yalnızca hesap yapar; internete çıkmaz.
"""
import json, os, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        raise SystemExit("eksik dosya: " + path)
    return json.load(open(path, encoding="utf-8"))


def real(roe, cpi):
    """Nominal özsermaye kârlılığını (%, yıllık) enflasyondan arındırır."""
    if roe is None or cpi is None:
        return None
    return ((1 + roe / 100.0) / (1 + cpi / 100.0) - 1) * 100.0


def l3pass(s):
    return s["B"] >= 2 and min(s["A"], s["C"], s["D"], s["E"]) >= 1


def run(cc):
    d = os.path.join(ROOT, "data", cc)
    P = load(os.path.join(ROOT, "pipeline", "params.json"))
    meta = load(os.path.join(d, "meta.json"))
    uni = load(os.path.join(d, "universe.json"))
    hist = load(os.path.join(d, "history.json"), {})
    reports = load(os.path.join(d, "reports.json"), {})
    cpi = meta["cpi"]
    years = meta["years"]                 # geçmiş dizilerindeki mali yıllar, eskiden yeniye; ardından "cur"
    era = meta.get("era") or (years + ["cur"])
    era_explicit = era != years + ["cur"]  # ülkeye özel dönem (örnek: Türkiye'de 2023 sonrası)
    era_years = [e for e in era if e != "cur"]
    cpi_years = sorted(y for y in cpi if y != "cur")

    def cpi_of(lab):
        """Bir mali yılın enflasyonu; şirketin mali yılı ülkenin yıl listesinin dışındaysa en yakın uç."""
        if lab == "cur" or not cpi_years:
            return cpi.get("cur")
        if lab in cpi:
            return cpi[lab]
        return cpi.get("cur") if lab > cpi_years[-1] else cpi[cpi_years[0]]

    def in_era(lab):
        if not era_explicit:
            return True
        return lab in era or (lab != "cur" and bool(era_years) and lab > max(era_years))
    deflate_all = meta.get("deflate", "all") == "all"
    mcap_min = meta["mcapMin"]

    U, L2 = [], {}
    for u in uni:
        c = u["c"]
        pe, pb = u.get("pe"), u.get("pb")
        roe = (pb / pe * 100.0) if (pe and pb and pe > 0 and pb > 0) else None
        defl = deflate_all or bool(u.get("nom"))
        rr = real(roe, cpi["cur"]) if defl else roe
        e, w = None, None
        if u.get("veh"):
            e, w = 1, "vehicle"
        elif not pe or pe <= 0:
            # kural aynı: pozitif F/K yoksa şirket 1. surda kalır. Yalnız neden doğru adlandırılır:
            # "noprofit" zarar olduğu biliniyor, "nodata" kaynak son 12 ayın kârını vermiyor, "nope" hangisi olduğu bilinmiyor
            e, w = 1, {"loss": "noprofit", "nodata": "nodata"}.get(u.get("np"), "nope")
        elif not pb or pb <= 0:
            e, w = 1, "equity"
        elif u["m"] < mcap_min:
            e, w = 1, "small"
        elif rr is None or rr < P["roeMin"]:
            e, w = 2, "roe_ttm"
        else:
            h = hist.get(c)
            if h is None:
                e, w = 2, "data"
                L2[c] = dict(asof=None, stale=1, roe=[None] * 6, rroe=[None] * 6, roic=[None] * 6,
                             fcf=[None] * 6, nd=None, pe=None, pb=None, dy=None, po=None, avg=None, mn=None,
                             fails=[{"k": "data"}], flags=[], ok=0)
            else:
                fy = h.get("fy") or years          # şirketin kendi mali yılları (kaynak sayfasındaki sütunlar)
                labs = [fy[i] if i < len(fy) and fy[i] else years[i] for i in range(5)] + ["cur"]
                roe6 = (list(h["roe"]) + [None] * 6)[:6]
                rroe6 = [(real(v, cpi_of(lab)) if defl else v) for lab, v in zip(labs, roe6)]
                fails, flags = [], []
                has_hist = (h["roe"][0] is not None) or (h.get("roic") and h["roic"][0] is not None)
                if h.get("stale"):
                    fails.append({"k": "data"})
                elif not has_hist:
                    fails.append({"k": "history"})
                loss = [lab for lab, v in zip(labs[:5], roe6[:5]) if v is not None and v < 0]
                if loss:
                    fails.append({"k": "loss", "v": loss})
                vals = [v for lab, v in zip(labs, rroe6) if v is not None and in_era(lab)]
                avg = mn = None
                if len(vals) >= 3:
                    avg, mn = sum(vals) / len(vals), min(vals)
                    if mn < P["eraMin"]:
                        fails.append({"k": "roe_min", "v": round(mn, 1)})
                    elif avg < P["eraAvg"]:
                        fails.append({"k": "roe_avg", "v": round(avg, 1)})
                elif not fails:
                    fails.append({"k": "history"})
                fin = bool(u.get("fin"))
                nd = h.get("nd")
                if not fin and nd is not None:
                    if nd > P["ndMax"]:
                        fails.append({"k": "debt", "v": round(nd, 1)})
                    elif nd > P["ndFlag"]:
                        flags.append({"k": "debt", "v": round(nd, 1)})
                if not fin:
                    f = [x for x in reversed(h["fcf"][1:]) if x is not None]   # son 12 ay + son dört mali yıl
                    pos = sum(1 for x in f if x > 0)
                    if len(f) >= 2:
                        if pos < 2 or pos / len(f) < 0.4:
                            fails.append({"k": "cash", "v": [pos, len(f)]})
                        elif pos / len(f) < 0.6:
                            flags.append({"k": "cash", "v": [pos, len(f)]})
                rnd = lambda x, d=1: None if x is None else round(x, d)
                L2[c] = dict(asof=h.get("asof"), stale=h.get("stale", 0), roe=roe6, rroe=[rnd(v, 2) for v in rroe6],
                             roic=h.get("roic"), fcf=h["fcf"], nd=nd, pe=h.get("pe"), pb=h.get("pb"), dy=h.get("dy"), po=h.get("po"),
                             avg=rnd(avg), mn=rnd(mn), fails=fails, flags=flags, ok=0 if fails else 1)
                if labs[:5] != years:
                    L2[c]["fy"] = labs[:5]
                if h.get("url"):
                    L2[c]["url"] = h["url"]
                if fails:
                    e, w = 2, fails[0]["k"]
                else:
                    rep = reports.get(c)
                    if not rep or "scores" not in rep:
                        e, w = 3, "pending"          # 2. suru geçti, 3. surda henüz okunmadı
                    elif not l3pass(rep["scores"]):
                        s = rep["scores"]
                        e, w = 3, ("moat" if s["B"] < 2 else "mgmt" if s["D"] < 1 else "fragile")
                    else:
                        e, w = 4, "price"            # kale ya da bekleme: fiyat testi istemcide de hesaplanır
        U.append(dict(c=c, n=u["n"], s=u["s"], p=u["p"], m=u["m"], f=u.get("f"), pe=pe, pb=pb, per=u.get("per"),
                      e=e, w=w, nom=1 if (u.get("nom") or deflate_all) else 0, fin=1 if u.get("fin") else 0,
                      roe=None if roe is None else round(roe, 1), rr=None if rr is None else round(rr, 1)))
        if u.get("pc"):
            U[-1]["pc"] = u["pc"]             # fiyatı ülkenin olağan biriminden farklı yazılan pay
        if u.get("pes"):
            U[-1]["pes"] = u["pes"]           # F/K, kaynağın başka bir son 12 ay alanından hesaplandı ("eps" ya da "roe")

    R = {c: r for c, r in reports.items() if c in L2 and L2[c]["ok"]}
    # 2. surda elenen ama açıklama gerektiren şirketler için kısa not (raporun tamamı gösterilmez)
    N = {c: r["note"] for c, r in reports.items() if c not in R and r.get("note")}
    out = dict(cc=cc, asof=meta["asof"], U=U, L2=L2, R=R, N=N)
    json.dump(out, open(os.path.join(d, "core.json"), "w", encoding="utf-8"), ensure_ascii=False)

    cnt = collections.Counter((u["e"], u["w"]) for u in U)
    print(cc, "evren", len(U), "| 1. suru geçen", sum(1 for u in U if u["e"] > 1), "| 2. suru geçen", sum(1 for u in U if u["e"] > 2),
          "| sırada", cnt.get((3, "pending"), 0), "| 3. suru geçen", sum(1 for u in U if u["e"] > 3))
    print("  ", dict(sorted(cnt.items(), key=lambda kv: (kv[0][0], -kv[1]))))
    # fiyat testi (istemcideki val() ile aynı formül)
    by = {u["c"]: u for u in U}
    for c, u in sorted(by.items()):
        if u["e"] != 4:
            continue
        l, s = L2[c], R[c]["scores"]
        cand = [x for x in (u["rr"] if u["nom"] else u["roe"], l["rroe"][-2], l["rroe"][-1]) if x is not None]
        roe_n = min(cand)
        pen = u["pb"] / (roe_n / 100.0)
        g = P["gWide"] if s["B"] >= 3 else P["gNarrow"]
        fair = 100.0 / (P["r"] - g)
        mos = (1 - pen / fair) * 100
        print(f"   {c:8} temkinli ROE {roe_n:5.1f} | temkinli F/K {pen:5.1f} | adil {fair:4.1f} | marj {mos:6.1f}% | "
              f"alım eşiği {u['p'] * fair * (1 - P['mos'] / 100) / pen:9.2f} | fiyat {u['p']} -> {'KALE' if mos >= P['mos'] else 'BEKLEME'}")
    return out


if __name__ == "__main__":
    for cc in sys.argv[1:] or ["TR"]:
        run(cc)
