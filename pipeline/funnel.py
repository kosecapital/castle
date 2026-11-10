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
    keys = years + ["cur"]
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
            e, w = 1, "noprofit"
        elif not pb or pb <= 0:
            e, w = 1, "equity"
        elif u["m"] < mcap_min:
            e, w = 1, "small"
        elif rr < P["roeMin"]:
            e, w = 2, "roe_ttm"
        else:
            h = hist.get(c)
            if h is None:
                e, w = 2, "data"
                L2[c] = dict(asof=None, stale=1, roe=[None] * len(keys), rroe=[None] * len(keys), roic=[None] * len(keys),
                             fcf=[None] * len(keys), nd=None, pe=None, pb=None, dy=None, po=None, avg=None, mn=None,
                             fails=[{"k": "data"}], flags=[], ok=0)
            else:
                roe_h = dict(zip(keys, h["roe"]))
                rroe_h = {k: (real(v, cpi.get(k)) if defl else v) for k, v in roe_h.items()}
                fails, flags = [], []
                first = years[0]
                has_hist = (h["roe"][0] is not None) or (h.get("roic") and h["roic"][0] is not None)
                if h.get("stale"):
                    fails.append({"k": "data"})
                elif not has_hist:
                    fails.append({"k": "history"})
                loss = [y for y in years if roe_h[y] is not None and roe_h[y] < 0]
                if loss:
                    fails.append({"k": "loss", "v": loss})
                vals = [rroe_h[k] for k in era if rroe_h.get(k) is not None]
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
                L2[c] = dict(asof=h.get("asof"), stale=h.get("stale", 0), roe=h["roe"], rroe=[rnd(rroe_h[k], 2) for k in keys],
                             roic=h.get("roic"), fcf=h["fcf"], nd=nd, pe=h.get("pe"), pb=h.get("pb"), dy=h.get("dy"), po=h.get("po"),
                             avg=rnd(avg), mn=rnd(mn), fails=fails, flags=flags, ok=0 if fails else 1)
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

    R = {c: r for c, r in reports.items() if c in L2 and L2[c]["ok"]}
    out = dict(cc=cc, asof=meta["asof"], U=U, L2=L2, R=R)
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
