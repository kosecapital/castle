#!/usr/bin/env python3
"""Büyüme yargısı: toplanan güncel gerçeklerden (data/<CC>/growth_facts.json) her şirketin `growth` kaydını aynı kuralla üretir
ve data/<CC>/reports.json içine yazar. Kural CLAUDE.md, "Büyüme yargısı" başlığındadır. İnternet kullanmaz.

  python3 pipeline/growth_judgment.py TR US     # bu ülkelerde gerçek kaydı olan şirketlerin yargısını yeniden yaz
Sonra: python3 pipeline/funnel.py <CC>
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
tr = lambda x, d=1: (f"{x:.{d}f}").replace(".", ",").replace("-", "−")
en = lambda x, d=1: (f"{x:.{d}f}").replace("-", "−")


def judge(f, gm, cpi, real_already):
    """Döner: growth kaydı (g None ise indirim yok)."""
    defl = (lambda p: p) if real_already else (lambda p: ((1 + p / 100.0) / (1 + cpi / 100.0) - 1) * 100.0)
    adj = f.get("adjusted") or {}
    ms = []                                              # (etiket tr, etiket en, nominal %, düzeltilmiş mi)
    exc = f.get("exclude") or {}                         # temsil etmeyen ölçü: gerekçesiyle dışarıda bırakılır (gerçek kaydında yazılır)
    for k, ak in (("ytd", "ytd_pct"), ("quarter", "quarter_pct")):
        m = f.get(k)
        if m and m.get("pct") is not None and k not in exc:
            a = adj.get(ak)
            ms.append((m["tr"], m["en"], a if a is not None else m["pct"], a is not None, m["pct"]))
    gd = f.get("guidance")
    if gd and gd.get("pct") is not None and "guidance" not in exc:
        ms.append((gd["tr"], gd["en"], gd["pct"], False, gd["pct"]))
    metric = {"EPS": ("hisse başına kâr", "earnings per share")}.get(f.get("metric"), ("net kâr", "net profit"))
    lst_tr = "; ".join(f"{a} %{tr(p)}" + (f" (şirketin düzeltilmiş rakamı; açıklanan %{tr(r)})" if adjd else "") for a, _, p, adjd, r in ms)
    lst_en = "; ".join(f"{b} {en(p)}%" + (f" (the company's adjusted figure; reported {en(r)}%)" if adjd else "") for _, b, p, adjd, r in ms)
    real_note_tr = " Rakamlar enflasyon muhasebesiyle hazırlandığı için zaten reeldir." if real_already else ""
    real_note_en = " The figures are prepared under inflation accounting, so they are already real." if real_already else ""
    head_tr = f"Formül yılda %{tr(gm)} büyüme veriyordu. En güncel veriler ({metric[0]}, yıllık değişim): {lst_tr}." + real_note_tr if ms else f"Formül yılda %{tr(gm)} büyüme veriyordu."
    head_en = f"The formula gave growth of {en(gm)}% a year. Latest figures ({metric[1]}, year on year): {lst_en}." + real_note_en if ms else f"The formula gave growth of {en(gm)}% a year."
    if adj.get("what_tr") and any(x[3] for x in ms):
        head_tr += " Düzeltme: " + adj["what_tr"].rstrip(".") + "."
        head_en += " Adjustment: " + adj["what_en"].rstrip(".") + "."
    for k, e in exc.items():
        head_tr += " " + e["tr"]; head_en += " " + e["en"]
    if f.get("note_tr"):
        head_tr += " " + f["note_tr"]; head_en += " " + f["note_en"]
    out = dict(g=None)
    perm, dep, skip = f.get("permanent"), f.get("departed"), f.get("skip")
    if perm:
        out.update(permanent=True)
        b_tr = head_tr + " " + perm["tr"].rstrip(".") + ". Kötüleşmenin nedeni kalıcı olduğu için şirket fiyat testine alınmadı."
        b_en = head_en + " " + perm["en"].rstrip(".") + ". Because the cause of the deterioration is lasting, the company was not taken to the price test."
    elif skip:
        b_tr, b_en = f"Formül yılda %{tr(gm)} büyüme veriyordu. " + skip["tr"], f"The formula gave growth of {en(gm)}% a year. " + skip["en"]
    elif dep and dep.get("remaining_pct") is not None:
        r = max(0.0, defl(dep["remaining_pct"]))
        b_tr = head_tr + " " + dep["tr"].rstrip(".") + f". Kalan işin büyümesi {dep['basis_tr'].rstrip('.')}: yılda %{tr(dep['remaining_pct'])}" + ("" if real_already else f", enflasyondan arındırılınca %{tr(r)}") + "."
        b_en = head_en + " " + dep["en"].rstrip(".") + f". Growth of the remaining business, {dep['basis_en'].rstrip('.')}: {en(dep['remaining_pct'])}% a year" + ("" if real_already else f", {en(r)}% after inflation") + "."
        if r < gm:
            out["g"] = round(r, 1)
            b_tr += f" Geçmiş büyüme yerine bu hız kullanıldı: %{tr(out['g'])}."; b_en += f" This rate was used instead of past growth: {en(out['g'])}%."
        else:
            b_tr += " Bu, formülün hızından düşük değil; hız indirilmedi."; b_en += " That is not below the formula's rate; the rate was not lowered."
    elif not ms:
        b_tr, b_en = head_tr + " Güncel büyüme verisi bulunamadı; hız indirilmedi.", head_en + " No recent growth figure was found; the rate was not lowered."
    else:
        rec = max(0.0, min(defl(p) for _, _, p, _, _ in ms))
        low_tr = f" En düşüğü" + ("" if real_already else ", enflasyondan arındırılınca,") + f" %{tr(rec)}" + (" (sıfırın altı sıfır sayılır)" if rec == 0 else "") + "."
        low_en = f" The lowest" + ("" if real_already else ", after inflation,") + f" is {en(rec)}%" + (" (below zero counts as zero)" if rec == 0 else "") + "."
        if gm <= 0:
            b_tr, b_en = head_tr + " Formül zaten sıfır büyüme varsayıyor; indirilecek bir şey yok.", head_en + " The formula already assumes zero growth; there is nothing to lower."
        elif rec < gm / 2.0:
            out["g"] = round((gm + rec) / 2.0, 1)
            b_tr = head_tr + low_tr + f" Bu, formülün hızının yarısından az olduğu için ikisinin ortası alındı: %{tr(out['g'])}."
            b_en = head_en + low_en + f" Because this is less than half the formula's rate, the midpoint of the two was used: {en(out['g'])}%."
        else:
            b_tr = head_tr + low_tr + " Bu, formülün hızının yarısından az değil; hız indirilmedi."
            b_en = head_en + low_en + " That is not less than half the formula's rate; the rate was not lowered."
    dv = f.get("dividend")
    if dv and dv.get("dps") and f.get("_price"):
        out["dy"] = round(100.0 * dv["dps"] / f["_price"], 1)
        b_tr += f" Kaynakta temettü verimi yok; şirketin {dv['for_tr']} için açıkladığı hisse başına {tr(dv['dps'], 0)} {dv['cur']} temettüden %{tr(out['dy'])} hesaplandı."
        b_en += f" The data source has no dividend yield; {en(out['dy'])}% was calculated from the dividend of {en(dv['dps'], 0)} {dv['cur']} per share the company declared for the {dv['for_en']}."
    out["basis"] = dict(tr=b_tr, en=b_en)
    return out


def run(cc):
    facts = json.load(open(J("data", cc, "growth_facts.json"), encoding="utf-8"))
    core = json.load(open(J("data", cc, "core.json"), encoding="utf-8"))
    meta = json.load(open(J("data", cc, "meta.json"), encoding="utf-8"))
    rp = J("data", cc, "reports.json")
    reports = json.load(open(rp, encoding="utf-8"))
    byc = {u["c"]: u for u in core["U"]}
    for c, f in facts.items():
        if c not in reports or c not in core["L2"] or "g" not in core["L2"][c]:
            continue
        l, u = core["L2"][c], byc[c]
        f = dict(f, _price=u["p"] if l.get("dy") is None or l.get("dyj") else None)
        rec = judge(f, l.get("gm", l["g"]), meta["cpi"]["cur"], not u["nom"])
        rec["per"] = u.get("per")
        reports[c]["growth"] = rec
        have = {s["u"] for s in reports[c]["sources"]}
        for k in ("ytd", "quarter", "guidance", "adjusted", "departed", "permanent", "dividend"):
            m = f.get(k) or {}
            if m.get("url") and m["url"] not in have:
                have.add(m["url"])
                reports[c]["sources"].append(dict(t="Büyüme yargısının kaynağı: " + (m.get("tr") or m.get("for_tr") or "şirket belgesi")[:80],
                                                  te="Source for the growth judgment: " + (m.get("en") or m.get("for_en") or "company document")[:80], u=m["url"]))
        print(f"  {cc} {c:10} formül {l.get('gm', l['g']):5} -> " + ("ELENDİ (kalıcı)" if rec.get("permanent") else "indirilmedi" if rec["g"] is None else f"{rec['g']}"))
    open(rp, "w", encoding="utf-8").write(json.dumps(reports, ensure_ascii=False, indent=1) + "\n")


if __name__ == "__main__":
    for cc in sys.argv[1:]:
        run(cc.upper())
