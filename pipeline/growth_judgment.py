#!/usr/bin/env python3
"""Kazanç ve büyüme yargısı: toplanan güncel gerçeklerden (data/<CC>/earn_facts.json, growth_facts.json) her şirketin `earn` ve
`growth` kaydını aynı kuralla üretir ve data/<CC>/reports.json içine yazar. Kurallar CLAUDE.md, "Kazanç yargısı" ve "Büyüme yargısı"
başlıklarındadır. İnternet kullanmaz. Sırası: kazanç yargısı, süzgeç (formülün büyüme hızı yeni kazançla hesaplanır), büyüme yargısı, süzgeç.

  python3 pipeline/growth_judgment.py TR US     # bu ülkelerde gerçek kaydı olan şirketlerin yargılarını yeniden yaz ve süzgeci çalıştır
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import funnel  # noqa: E402

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


tr_en = lambda x: en(x, 0)


def judge_earn(f):
    """Kazanç yargısı. Döner: earn kaydı (k = 1 ise indirim yok). Yalnız indirir.
    Tek seferlik kazançlar (eksi aynı dönemin tek seferlik giderleri) son 12 ay kârının %3'ünü geçiyorsa o oran düşülür.
    Şirketin kendi hisse başına kâr beklentisi son 12 ayın altındaysa kazanç o orana indirilir. İkisinden düşük olan çarpan alınır."""
    eps, cur = (f.get("ttm") or {}).get("eps"), f.get("eps_cur") or ""
    gs, os_ = f.get("gains") or [], f.get("offsets") or []
    net = sum(g["frac"] for g in gs) - sum(o["frac"] for o in os_)
    k_one = 1 - net if net >= 0.03 else 1.0
    gd = [g for g in (f.get("guidance") or []) if eps]
    low = min(gd, key=lambda g: g["mid"]) if gd else None
    k_g = min(1.0, low["mid"] / eps) if low else 1.0
    src = f.get("_src")                                  # kaynağın F/K'sının ima ettiği kâr ile şirketin belgesindeki kâr (aynı birim)
    k_src = src["doc"] / src["implied"] if src and src["doc"] / src["implied"] < 0.97 else 1.0
    k = max(0.2, round(k_src * min(k_one, k_g), 3))
    p = lambda x: tr(100 * x)
    q = lambda x: en(100 * x)
    b_tr, b_en = "Hesap son 12 ayın kârına dayanır.", "The calculation rests on the profit of the last 12 months."
    if k_src < 1:
        b_tr += f" Kaynağın F/K'sı son 12 ay için {src['tr'](src['implied'])} kâr ima ediyor; şirketin kendi tablolarından toplanan son 12 ay kârı {src['tr'](src['doc'])}. Farkın nedeni bulunamadı; şirketin belgesi esas alındı ve kazanç bu orana indirildi (%{p(1 - k_src)})."
        b_en += f" The data source's P/E implies a last-12-month profit of {src['en'](src['implied'])}; the last-12-month profit added up from the company's own statements is {src['en'](src['doc'])}. The reason for the gap was not found; the company's document was taken as the basis and earnings were lowered to that ratio ({q(1 - k_src)}%)."
    if gs:
        tax_tr = lambda g: " (vergi öncesi tutar; vergi etkisi açıklanmadığı için düşülmedi)" if g.get("how") == "pretax" else ""
        tax_en = lambda g: " (pre-tax amount; the tax effect is not disclosed, so it was not deducted)" if g.get("how") == "pretax" else ""
        b_tr += " Bu kârın içindeki tek seferlik kazançlar: " + "; ".join(f"{g['tr']}: son 12 ay kârının %{p(g['frac'])} kadarı{tax_tr(g)}" for g in gs) + "."
        b_en += " One-off gains inside that profit: " + "; ".join(f"{g['en']}: {q(g['frac'])}% of last-12-month profit{tax_en(g)}" for g in gs) + "."
    if os_:
        b_tr += " Aynı dönemin tek seferlik giderleri: " + "; ".join(f"{o['tr']}: %{p(o['frac'])}" for o in os_) + "."
        b_en += " One-off charges in the same period: " + "; ".join(f"{o['en']}: {q(o['frac'])}%" for o in os_) + "."
    if f.get("drop"):
        b_tr += " " + f["drop"]["tr"]; b_en += " " + f["drop"]["en"]
    if gs or os_:
        if net >= 0.03:
            b_tr += f" Net etki %{p(net)}; kazanç bu kadar indirildi."; b_en += f" The net effect is {q(net)}%; earnings were lowered by that much."
        elif net > 0:
            b_tr += f" Net etki %{p(net)}; %3'ün altında olduğu için dikkate alınmadı."; b_en += f" The net effect is {q(net)}%; being under 3%, it was disregarded."
        else:
            b_tr += " Giderler kazançlardan büyük; kazanç indirilmedi (yargı kazancı yükseltmez)."; b_en += " The charges exceed the gains; earnings were not lowered (the judgment never raises earnings)."
    if low:
        kind_tr = " (şirketin düzeltilmiş ölçüsü)" if low.get("kind") == "adjusted" else ""
        kind_en = " (the company's adjusted measure)" if low.get("kind") == "adjusted" else ""
        b_tr += f" Şirketin {low['fy_tr']} için hisse başına kâr beklentisi {tr(low['mid'], 2)} {cur}{kind_tr}; son 12 ayda {tr(eps, 2)} {cur}."
        b_en += f" The company's earnings-per-share outlook for {low['fy_en']} is {en(low['mid'], 2)} {cur}{kind_en}; the last 12 months were {en(eps, 2)} {cur}."
        if k_g < 1:
            b_tr += f" Beklenti daha düşük olduğu için kazanç bu orana indirildi (%{p(1 - k_g)})."; b_en += f" Because the outlook is lower, earnings were lowered to that ratio ({q(1 - k_g)}%)."
        else:
            b_tr += " Beklenti daha düşük değil."; b_en += " The outlook is not lower."
    elif not (gs or os_ or f.get("drop") or k_src < 1):
        b_tr += " Şirket hisse başına kâr beklentisi açıklamıyor; son 12 ayda tek seferlik sayılacak önemli bir kazanç bulunmadı. Kazanç olduğu gibi alındı."
        b_en += " The company gives no earnings-per-share outlook, and no material one-off gain was found in the last 12 months. Earnings were taken as they are."
    cur_tr = "TL" if cur == "TRY" else cur
    mo = f.get("monetary")                               # enflasyon muhasebesinin net parasal pozisyon kalemi: gösterilir, düşülmez
    if mo and mo.get("amount") and mo.get("pretax"):
        sh, amt = abs(mo["amount"]) / mo["pretax"], abs(mo["amount"]) / 1000.0
        if mo["amount"] > 0:
            b_tr += (f" {mo['tr']} vergi öncesi kârının %{tr(100 * sh, 0)} kadarı ({tr(amt)} milyar {cur_tr}) net parasal pozisyon kazancıdır. Bu kalem enflasyon muhasebesinden gelir:"
                     " şirketin borçları enflasyonla erir; aynı tabloda stoklar, amortisman ve öbür giderler enflasyonla yukarı düzeltilir ve faaliyet kârını düşürür. İkisi aynı düzeltmenin iki yüzüdür;"
                     " bu yüzden kalem tek seferlik sayılmadı ve kazançtan düşülmedi. Büyüklüğü enflasyona ve borcun para birimine bağlıdır, yıldan yıla değişir.")
            b_en += (f" {tr_en(100 * sh)}% of pre-tax profit for {mo['en']} ({en(amt)} billion {cur}) is a net monetary position gain. This item comes from inflation accounting:"
                     " inflation erodes the company's liabilities, while in the same statement inventories, depreciation and other costs are restated upwards and reduce operating profit. The two are two sides of one adjustment,"
                     " so the item was not treated as a one-off and was not deducted. Its size depends on inflation and on the currency of the debt, and changes from year to year.")
        else:
            b_tr += (f" {mo['tr']} kârı, {tr(amt)} milyar {cur_tr} net parasal pozisyon kaybından sonradır (vergi öncesi kârın %{tr(100 * sh, 0)} kadarı): şirketin elindeki nakit ve alacaklar enflasyonla eridi."
                     " Bu kayıp kârdan zaten düşülmüş durumda; kazanç yükseltilmedi.")
            b_en += (f" Profit for {mo['en']} is after a net monetary position loss of {en(amt)} billion {cur} (equal to {tr_en(100 * sh)}% of pre-tax profit): inflation eroded the company's cash and receivables."
                     " That loss is already deducted from profit; earnings were not raised.")
    if k < 1:
        b_tr += f" Son 12 ayın kârı {tr(k, 2)} ile çarpılarak kullanıldı."; b_en += f" Last-12-month profit was used multiplied by {en(k, 2)}."
    return dict(k=k, basis=dict(tr=b_tr, en=b_en))


def run_earn(cc):
    p = J("data", cc, "earn_facts.json")
    if not os.path.exists(p):
        return
    facts = json.load(open(p, encoding="utf-8"))
    core = json.load(open(J("data", cc, "core.json"), encoding="utf-8"))
    rp = J("data", cc, "reports.json")
    reports = json.load(open(rp, encoding="utf-8"))
    byc = {u["c"]: u for u in core["U"]}
    meta = json.load(open(J("data", cc, "meta.json"), encoding="utf-8"))
    curs = {meta.get("cur"), (meta.get("en") or {}).get("cur")}
    for c, f in facts.items():
        if c not in reports or c not in byc:
            continue
        # Kaynak ile belge aynı kârı mı söylüyor? Yalnız birimler aynıysa karşılaştırılır (hisse başına kâr tercih edilir).
        u, t, ec = byc[c], f.get("ttm") or {}, f.get("eps_cur") or ""
        if u.get("pe") and u["pe"] > 0 and ec in curs:
            if t.get("eps"):
                f = dict(f, _src=dict(doc=t["eps"], implied=u["p"] / u["pe"], tr=lambda x, ec=ec: f"hisse başına {tr(x, 2)} {ec}", en=lambda x, ec=ec: f"{en(x, 2)} {ec} per share"))
            elif t.get("net_profit") and f.get("unit") == "million " + ec:
                f = dict(f, _src=dict(doc=t["net_profit"], implied=u["m"] / u["pe"], tr=lambda x, ec=ec: f"{tr(x / 1000.0)} milyar {'TL' if ec == 'TRY' else ec}", en=lambda x, ec=ec: f"{en(x / 1000.0)} billion {ec}"))
        rec = judge_earn(f)
        rec["per"] = byc[c].get("per")
        reports[c]["earn"] = rec
        have = {s["u"] for s in reports[c]["sources"]}
        for m in [f.get("ttm") or {}] + (f.get("gains") or []) + (f.get("guidance") or []) + [f.get("monetary") or {}]:
            if m.get("url") and m["url"] not in have:
                have.add(m["url"])
                reports[c]["sources"].append(dict(t="Kazanç yargısının kaynağı", te="Source for the earnings judgment", u=m["url"]))
        if rec["k"] < 1:
            print(f"  {cc} {c:10} kazanç çarpanı {rec['k']}")
    open(rp, "w", encoding="utf-8").write(json.dumps(reports, ensure_ascii=False, indent=1) + "\n")


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
        rec = judge(f, l.get("gm", l["g"]), meta["cpi"]["cur"], not u["nom"] and not l.get("fx"))
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
        cc = cc.upper()
        run_earn(cc)
        funnel.run(cc)        # formülün büyüme hızı yeni kazançla
        run(cc)
        funnel.run(cc)
