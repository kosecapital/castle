#!/usr/bin/env python3
"""Castle süzgeci, genç Buffett yöntemi (Alper'in 24 Kasım 2026 kararı).

Buffett'ın ortaklık yıllarındaki (1956-1969) gibi: hendek ve kalite elemesi yok; fiyatın değerin çok altında olduğu yerleri
dört mercekle arar. Bir şirket hangi mercekten geçerse "fırsat" listesine girer; hiçbir mercek "al" demek değildir.

  1. Net-net (Graham): piyasa değeri ≤ net dönen varlık değerinin (NCAV) üçte ikisi.
     NCAV = dönen varlıklar − bütün yükümlülükler − azınlık payları.
  2. Graham'ın girişimci yatırımcı ölçütleri (Akıllı Yatırımcı, 15. bölüm): cari oran ≥ 1,5; uzun vadeli finansal borç ≤ net işletme
     sermayesinin %110'u; son beş mali yılda zarar yok; temettü ödüyor; son yılın reel kârı dört yıl öncekinden yüksek;
     piyasa değeri ≤ maddi özsermayenin %120'si.
  3. Kâr verimi ve faiz: reel kâr verimi (1 ÷ F/K) ≥ getiri eşiği. Eşik = en az `r` (%10), reel tahvil getirisi bunun yarısından
     yüksekse onun iki katı (Graham: kâr verimi en az yüksek notlu tahvilin iki katı). Enflasyon muhasebesi uygulamayan şirkette
     reel kâr = kâr − enflasyon × özsermaye (sermayeyi korumak için gereken pay).
  4. Özel durumlar (workout): pay alım teklifi, borsadan çıkarma, birleşme. Teklif fiyatı ile bugünkü fiyat arasındaki farkın yıllık
     getirisi 10 yıllık devlet tahvili getirisini geçiyorsa listeye girer. Kayıtlar data/TR/special.json içindedir (Claude yazar, KAP'tan).

Girdi  (data/<CC>/): meta.json, universe.json, fin.json (mali tablolar; yoksa ilk iki mercek ölçülemez), special.json, flags.json, reports.json
Çıktı  (data/<CC>/core.json)
Kullanım: python3 pipeline/funnel.py TR     (internete çıkmaz)
"""
import datetime, json, math, os, statistics, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
NO_SHEET = {"Bankacılık", "Sigorta", "Fin.Kiralama ve Faktoring", "Aracı Kurumlar", "Varlık Yönetim"}


def load(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        raise SystemExit("eksik dosya: " + path)
    return json.load(open(path, encoding="utf-8"))


def rates(meta, P):
    """Faiz ve enflasyon: meta.json içindeki `rates` (Claude'un kaynaklı yazdığı) önce, yoksa toplayıcının getirdiği."""
    r = dict(meta.get("rates_in") or {})
    r.update({k: v for k, v in (meta.get("rates") or {}).items() if v is not None})
    pi = r.get("pi", (meta.get("cpi") or {}).get("cur"))
    y10 = r.get("y10")
    out = dict(y10=y10, y10_src=r.get("y10_src"), y10_date=r.get("y10_date"), policy=r.get("policy"), policy_src=r.get("policy_src"),
               pi=pi, pi_src=r.get("pi_src") or "meta.cpi.cur")
    out["real"] = None if (y10 is None or pi is None) else round(((1 + y10 / 100) / (1 + pi / 100) - 1) * 100, 2)
    out["hurdle"] = round(max(P["r"], P["bondMult"] * out["real"]) if out["real"] is not None else P["r"], 2)
    return out


def fin_unit(uni, fin):
    """Mali tabloların birimi: piyasa değeri milyon TL; tablo TL ya da bin TL olabilir. Ana ortaklık özsermayesi ≈ piyasa değeri ÷ PD/DD."""
    rs = []
    for u in uni:
        f = fin.get(u["c"])
        if not f or not u.get("pb") or u["pb"] <= 0:
            continue
        e = (f.get("sheet") or {}).get("eqp") or (f.get("sheet") or {}).get("eq")
        if e and e > 0:
            rs.append(e / (u["m"] / u["pb"]))
    if len(rs) < 20:
        return None, None
    med = statistics.median(rs)
    k = 10 ** round(math.log10(med))
    return k, round(med / k, 3)          # birim (1e6: TL, 1e3: bin TL) ve tutarlılık (1'e yakın olmalı)


def deflator(meta, fy, y):
    """y yılının kârını fy yılının parasına çevirir (yıl sonu TÜFE). meta.fin_restated doğruysa kaynak zaten aynı paradadır."""
    if meta.get("fin_restated"):
        return 1.0
    cpi, k = meta.get("cpi") or {}, 1.0
    for z in range(int(y) + 1, int(fy) + 1):
        c = cpi.get(str(z))
        if c is None:
            return None
        k *= 1 + c / 100.0
    return k


def graham(u, f, unit, meta, P):
    """Girişimci yatırımcı ölçütleri. Döner: dict (değerler ve altı denetim)."""
    s = {k: (v / unit if v is not None else None) for k, v in (f.get("sheet") or {}).items()}
    ca, cl, ncl, fd_lt = s.get("ca"), s.get("cl"), s.get("ncl"), s.get("fd_lt") or 0.0
    eqp = s.get("eqp") if s.get("eqp") is not None else s.get("eq")
    wc = None if ca is None or cl is None else ca - cl
    cr = None if not ca or not cl else ca / cl
    tang = None if eqp is None else eqp - (s.get("intg") or 0.0) - (s.get("gw") or 0.0)
    ann = f.get("ann") or {}
    fy = int(f.get("fy") or 0)
    yrs = [str(y) for y in range(fy, fy - P["grYears"], -1)]
    nps = [(y, (ann.get(y) or {}).get("np")) for y in yrs]
    have = [(y, v / unit) for y, v in nps if v is not None]
    loss = [y for y, v in have if v <= 0]
    g = None
    first, last = (ann.get(yrs[-1]) or {}).get("np"), (ann.get(yrs[0]) or {}).get("np")
    dfl = deflator(meta, yrs[0], yrs[-1])
    if first is not None and last is not None and dfl and first > 0:
        g = round(((last / (first * dfl)) - 1) * 100, 1)        # son yılın reel kârının dört yıl öncekine göre değişimi (%)
    div = ((ann.get(yrs[0]) or {}).get("div") or 0) != 0 or ((f.get("ytd") or {}).get("div") or 0) != 0   # son mali yılda ya da bu yıl ödenen temettü
    ptb = None if not tang or tang <= 0 else u["m"] / tang
    checks = [
        ("cr", cr is not None and cr >= P["grCurrent"]),
        ("debt", wc is not None and wc > 0 and fd_lt <= P["grDebtWC"] * wc),
        ("stable", len(have) >= P["grYears"] and not loss and (u.get("pe") or 0) > 0),
        ("div", bool(div)),
        ("growth", g is not None and g > 0),
        ("ptb", ptb is not None and ptb <= P["grPTB"]),
    ]
    return dict(cr=None if cr is None else round(cr, 2), wc=None if wc is None else round(wc, 1), ltd=round(fd_lt, 1),
                dwc=None if not wc or wc <= 0 else round(fd_lt / wc, 2), tang=None if tang is None else round(tang, 1),
                ptb=None if ptb is None else round(ptb, 2), yrs=len(have), loss=loss, g=g, div=bool(div),
                np={y: round(v, 1) for y, v in have}, ok={k: v for k, v in checks}, n=sum(1 for _, v in checks if v))


def netnet(u, f, unit):
    s = {k: (v / unit if v is not None else None) for k, v in (f.get("sheet") or {}).items()}
    ca, cl, ncl = s.get("ca"), s.get("cl"), s.get("ncl")
    tl = None
    if cl is not None and ncl is not None:
        tl = cl + ncl
    elif s.get("ta") is not None and s.get("eq") is not None:
        tl = s["ta"] - s["eq"]
    if ca is None or tl is None:
        return None
    mi = s.get("mi")
    if mi is None and s.get("eq") is not None and s.get("eqp") is not None:
        mi = s["eq"] - s["eqp"]
    ncav = ca - tl - max(mi or 0.0, 0.0)
    cash = (s.get("cash") or 0.0) + (s.get("fi") or 0.0)
    debt = (s.get("fd_st") or 0.0) + (s.get("fd_lt") or 0.0)
    return dict(ca=round(ca, 1), tl=round(tl, 1), mi=round(mi or 0.0, 1), ncav=round(ncav, 1), cash=round(cash, 1), debt=round(debt, 1),
                inv=None if s.get("inv") is None else round(s["inv"], 1), rec=None if s.get("rec") is None else round(s["rec"], 1),
                r=None if ncav <= 0 else round(u["m"] / ncav, 3))


def workout(u, w, asof, R, P):
    """Özel durum: teklif fiyatı, bugünkü fiyat, kalan gün, yıllık getiri."""
    if w.get("status") in ("done", "cancelled"):
        return dict(w, st="closed")
    offer = w.get("offer")
    end = w.get("pay") or w.get("end")
    out = dict(w)
    if offer is None or not u.get("p"):
        out["st"] = None
        return out
    sp = offer / u["p"] - 1
    out["spread"] = round(sp * 100, 2)
    if end:
        days = (datetime.date.fromisoformat(end) - datetime.date.fromisoformat(asof)).days
        out["days"] = days
        if days >= P["wsMinDays"] and sp > -0.99:
            out["ann"] = round(((1 + sp) ** (365.0 / days) - 1) * 100, 1)
    bar = R.get("y10") if R.get("y10") is not None else R.get("policy")
    out["bar"] = bar
    if w.get("status") == "pending":                       # fiyat ya da onay kesin değil: yalnız fark gösterilir
        out["st"] = "near" if sp > 0 else None
        return out
    out["st"] = "pass" if (out.get("ann") is not None and bar is not None and out["ann"] >= bar and sp > 0) else ("near" if sp > 0 else None)
    return out


def run(cc):
    d = J("data", cc)
    P = load(J("pipeline", "params.json"))
    meta, uni = load(os.path.join(d, "meta.json")), load(os.path.join(d, "universe.json"))
    fin, spec, flags = load(os.path.join(d, "fin.json"), {}), load(os.path.join(d, "special.json"), {}), load(os.path.join(d, "flags.json"), {})
    reps = load(os.path.join(d, "reports.json"), {})
    R = rates(meta, P)
    unit, unit_chk = fin_unit(uni, fin)
    fl = meta.get("flags", {})
    veh, nom, nomc = set(fl.get("veh", [])), set(fl.get("nom", [])), set(fl.get("nom_codes", []))
    asof = meta.get("asof")
    U, counts = [], dict(n=len(uni), size=0, nn=0, gr=0, ey=0, ws=0, any=0, fin=0)
    for u in uni:
        c = u["c"]
        row = {k: u.get(k) for k in ("c", "n", "s", "p", "m", "f", "pe", "pb", "per")}
        row["veh"] = 1 if u["s"] in veh else 0
        row["nom"] = 1 if (u["s"] in nom or c in nomc) else 0
        big = u["m"] >= P["mcapMin"] and (u.get("f") is None or u["m"] * u["f"] / 100.0 >= P["floatMin"])
        row["big"] = 1 if big else 0
        counts["size"] += big
        lens, near = [], []
        f = fin.get(c) if unit else None
        row_f = f
        if f and u["s"] not in NO_SHEET and f.get("per") == u.get("per"):
            counts["fin"] += 1
            nn = netnet(u, f, unit)
            if nn:
                row["nn"] = nn
                if nn["r"] is not None and big:
                    if nn["r"] <= P["nnBuy"]:
                        lens.append("nn")
                    elif nn["r"] <= P["nnNear"]:
                        near.append("nn")
            if not row["veh"]:
                gr = graham(u, f, unit, meta, P)
                row["gr"] = gr
                if big and gr["n"] == 6:
                    lens.append("gr")
                elif big and gr["n"] == 5:
                    near.append("gr")
        elif f and f.get("per") != u.get("per"):
            row["fin_old"] = f.get("per")
        # 3. kâr verimi. Son 12 ayın kârı, son üç mali yılın reel ortalamasından yüksekse ortalama alınır (Graham: tek yılın kârına
        #    değil, birkaç yılın ortalamasına bak; tek seferlik kazanç ve döngünün iyi yılı böyle ayıklanır).
        if u.get("pe") and u["pe"] > 0 and not row["veh"]:
            e_ttm = u["m"] / u["pe"]
            e = e_ttm
            gr = row.get("gr")
            if gr and gr.get("np") and f:
                fy = int(f.get("fy") or 0)
                vals = []
                for y in (fy, fy - 1, fy - 2):
                    v = gr["np"].get(str(y))
                    k = deflator(meta, fy, y)
                    if v is not None and k:
                        vals.append(v * k)
                if len(vals) == 3:
                    mo = max(0, (datetime.date.fromisoformat(asof) - datetime.date(fy, 12, 31)).days) / 365.0
                    avg = sum(vals) / 3 * (1 + (R["pi"] or 0) / 100.0) ** mo      # bugünün parasına
                    row["e3"] = round(avg, 1)
                    if avg < e_ttm:
                        e = max(avg, 0.0)
                        row["eavg"] = 1
            ey = 100.0 * e / u["m"]
            if row["nom"] and u.get("pb") and R["pi"] is not None:
                ey -= R["pi"] / u["pb"]          # enflasyon muhasebesi yok: özsermayeyi korumak için gereken pay düşülür
            row["ey"] = round(ey, 2)
            if u["pe"] < 2.5:
                row["eyw"] = 1                   # F/K 2,5'in altında: kârın büyük kısmı tek seferlik olabilir; okuyan oturum bakar
            if big and ey >= R["hurdle"]:
                lens.append("ey")
            elif big and ey >= P["eyNear"] * R["hurdle"]:
                near.append("ey")
        if c in spec:
            ws = workout(u, spec[c], asof, R, P)
            row["ws"] = ws
            if ws.get("st") == "pass":
                lens.append("ws")
            elif ws.get("st") == "near":
                near.append("ws")
        if c in flags:
            row["flag"] = flags[c]
            row["L"], row["near"] = [], []
            row["out"] = lens + near
        else:
            row["L"], row["near"] = lens, near
        for k in row["L"]:
            counts[k] += 1
        counts["any"] += 1 if row["L"] else 0
        U.append(row)
    core = dict(cc=cc, asof=asof, rates=R, unit=unit, unit_chk=unit_chk, fin_per=max((f.get("got") or "" for f in fin.values()), default=None) if fin else None,
                P=P, counts=counts, U=U, R={c: r for c, r in reps.items() if c in {u["c"] for u in uni}})
    json.dump(core, open(os.path.join(d, "core.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    return core


def summary(core):
    k = core["counts"]
    R = core["rates"]
    print(f'{core["cc"]} evren {k["n"]} | büyüklük süzgecini geçen {k["size"]} | mali tablosu olan {k["fin"]} (birim {core["unit"]}, tutarlılık {core["unit_chk"]})')
    print(f'  faiz: 10 yıllık {R["y10"]} | enflasyon {R["pi"]} | reel {R["real"]} | kâr verimi eşiği %{R["hurdle"]}')
    print(f'  net-net {k["nn"]} | Graham {k["gr"]} | kâr verimi {k["ey"]} | özel durum {k["ws"]} | en az bir mercekten geçen {k["any"]}')
    top = sorted([u for u in core["U"] if u["L"]], key=lambda u: (-len(u["L"]), -(u.get("ey") or 0)))
    for u in top[:25]:
        nn = u.get("nn") or {}
        print(f'   {u["c"]:7} {u["n"][:28]:28} {",".join(u["L"]):10} F/K {u.get("pe")} PD/DD {u.get("pb")} kâr verimi {u.get("ey")} NCAV oranı {nn.get("r")}')


if __name__ == "__main__":
    for cc in (sys.argv[1:] or ["TR"]):
        summary(run(cc.upper()))
