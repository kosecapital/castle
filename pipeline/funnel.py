#!/usr/bin/env python3
"""Castle süzgeci: bir ülkenin normalleştirilmiş verisinden dört surun sonucunu üretir.

Girdi  (data/<CC>/): meta.json, universe.json, history.json, reports.json (olmayabilir), finarm.json (olmayabilir)
Çıktı  (data/<CC>/core.json): {cc, asof, U, L2, R, RX, N, F}
        R: 2. suru geçen şirketlerin raporları | RX: raporu yazılmış, sonra 1. ya da 2. surda elenmiş şirketlerin saklanan raporları
        N: elenen şirketin kısa notu | F: finansman kolu düzeltmesi (uygulandıysa on=1, rakamı eskidiyse on=0)

Kullanım: python3 pipeline/funnel.py TR
Kurallar pipeline/params.json içindedir; ülkeye özgü ayarlar meta.json içindedir.
Bu betik yalnızca hesap yapar; internete çıkmaz.
"""
import math, json, os, sys, collections

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


def arm_ratio(fa, nd, per):
    """Finansman kolu hariç net borç/FAVÖK; düzeltme uygulanamıyorsa None.

    Bir sanayi şirketi bir finansman şirketini (taşıt ya da tüketici kredisi veren kol) tam konsolide ediyorsa kaynağın
    net borç/FAVÖK oranı o kolun borcunu da içerir. O borç, kolun verdiği kredilerin karşılığıdır; FAVÖK ile ölçülmez
    (banka ve finans şirketlerine borç testi uygulanmamasıyla aynı gerekçe). Eşik değişmez; ölçülen şey kolun dışındaki iştir:

        kaynağın FAVÖK'ü   = konsolide net borç ÷ kaynağın oranı
        kol hariç FAVÖK    = kaynağın FAVÖK'ü − kolun son 12 aydaki esas faaliyet kârı
        kol hariç oran     = kol hariç net borç ÷ kol hariç FAVÖK

    fa: data/<CC>/finarm.json kaydı. nd_all (konsolide net borç), nd_ex (kol hariç net borç) ve op_arm (kolun faaliyet kârı)
    aynı birimdedir (milyon, ülkenin para birimi) ve şirketin aynı tarihli, açıklanmış rakamlarıdır. Kayıt yalnız yazıldığı
    bilanço dönemi (per) için geçerlidir: evrendeki dönem değişince düzeltme düşer, kaynağın oranı olduğu gibi uygulanır."""
    try:
        a, x, o = float(fa["nd_all"]), float(fa["nd_ex"]), float(fa["op_arm"])
    except (KeyError, TypeError, ValueError):
        return None
    if nd is None or nd <= 0 or not per or fa.get("per") != per or not fa.get("sources") or a <= 0 or x > a or o < 0:
        return None
    ebitda = a / nd - o
    return x / ebitda if ebitda > 0 else None


def fair_value(P, roe_n, g, dy, wide):
    """4. sur: adil F/K (temkinli kazancın katı). İki ölçü birden; adil olan ikisinin düşüğüdür. Sayfadaki val() ile aynı hesap.
    İNA: iki aşamalı indirgenmiş nakit akışı. İlk gYears yıl şirketin büyüme hızı g, sonra hendek sınıfının kalıcı büyümesi. Her yıl ortağa
         kalan nakit = kâr × (1 − büyüme ÷ özsermaye kârlılığı): büyümeyi finanse eden kâr nakit sayılmaz. İskonto: reel getiri eşiği r.
    PEG: adil F/K = reel büyüme hızı (%) + temettü verimi (%). PEG büyüme için ödenen fazlayı sınırlar; değeri, şirket hiç büyümese
         edeceği tutarın (g = 0 ile İNA) altına indirmez: büyümeyen şirkette PEG sıfıra yaklaşır, bu bir değerleme değildir."""
    r, gt, n = P["r"] / 100.0, (P["gWide"] if wide else P["gNarrow"]) / 100.0, int(P["gYears"])
    g = max(0.0, min(g or 0.0, P["gCap"], roe_n)) / 100.0
    roe = roe_n / 100.0
    q = (1 + g) / (1 + r)
    stage1 = (1 - g / roe) / (1 + r) * sum(q ** t for t in range(n))
    stage2 = (1 + g) ** (n - 1) * (1 + gt) * (1 - gt / roe) / max(0.005, r - gt) / (1 + r) ** n
    dcf = max(0.01, stage1 + stage2)
    peg = max(0.0, g * 100.0 + max(0.0, dy or 0.0))
    dcf0 = 1 / (1 + r) * sum((1 / (1 + r)) ** t for t in range(n)) + (1 + gt) * (1 - gt / roe) / max(0.005, r - gt) / (1 + r) ** n   # g = 0
    lim = max(peg, dcf0)
    return dict(dcf=dcf, peg=peg, dcf0=dcf0, fair=min(dcf, lim), by="dcf" if dcf <= lim else ("peg" if peg >= dcf0 else "dcf0"))


def roe_cons(u, l):
    """Temkinli özsermaye kârlılığı: son 12 ay ve son iki mali yıl okumasının en düşüğü (reel)."""
    ek = l.get("ek") or 1.0            # kazanç yargısı: son 12 ayın kârı tek seferlik kazanç ya da daha düşük şirket beklentisi için indirilir
    ttm = u["rr"] if u["nom"] else u["roe"]
    return min(x for x in (None if ttm is None else ttm * ek, l["rroe"][-2], None if l["rroe"][-1] is None else l["rroe"][-1] * ek) if x is not None)


def price_test(P, u, l, wide):
    """Bir şirketin fiyat testi: temkinli F/K, adil F/K (İNA ve PEG), güvenlik marjı."""
    roe_n = roe_cons(u, l)
    pen = u["pb"] / (roe_n / 100.0)
    fv = fair_value(P, roe_n, l.get("g"), l.get("dy"), wide)
    return dict(fv, roe_n=roe_n, pen=pen, mos=(1 - pen / fv["fair"]) * 100)


def growth(h, labs, cpi_of, roe_n, ias29, P, first=None):
    """Şirketin büyüme hızı (reel, %): geçmiş ile sürdürülebilir olanın düşüğü, 0 ile gCap arasında.
    Geçmiş (gh): son beş mali yılın reel hisse başına kâr eğilimi. Net kâr = piyasa değeri ÷ F/K (oran sayfası); pay sayısındaki değişim
        "Buyback Yield / Dilution" satırından; her yıl o yılın tüketici enflasyonuyla düzeltilir; uçlara değil beş yılın eğilimine bakılır
        (logaritmik doğrusal eğim, en az dört yıl). Enflasyon muhasebesi (TMS 29) uygulayan şirkette kaynak her mali yılı bir sonraki
        yılın sonundaki parayla (ertesi yılın raporundaki karşılaştırmalı sütun), son mali yılı ise kendi yıl sonu parasıyla verir
        (Ford Otosan'da 2023 ve 2024 rakamlarıyla doğrulandı); düzeltme buna göre yapılır ve yalnız `first` yılından sonrası kullanılır.
    Sürdürülebilir (gs): temkinli özsermaye kârlılığı × dağıtılmayan kâr oranı (dağıtım oranı: mali yılların ortancası ile en güncel
        oranın yükseği).
    Döner: (kullanılan, gh, gs, dağıtım oranı)."""
    fy_po = [x for x in (h.get("pos") or [])[:5] if x is not None]
    pos = sorted(fy_po)
    po = pos[len(pos) // 2] if pos else h.get("po")
    allp = h.get("pos") or []
    last = allp[5] if len(allp) > 5 and allp[5] is not None else (fy_po[-1] if fy_po else None)
    if last is not None and po is not None:
        po = max(po, last)                                 # en güncel dağıtım oranı (son 12 ay) ortancadan yüksekse o alınır (temkinli)
    po = max(0.0, min(100.0, po or 0.0))
    gs = roe_n * (1 - po / 100.0)
    gh = None
    mc, pes, bb = h.get("mc"), h.get("pes"), h.get("bb") or [None] * 6
    if mc and pes:
        cum = [1.0]
        for i in range(1, 5):
            cum.append(cum[-1] * (1 + (cpi_of(labs[i]) or 0.0) / 100.0))
        pts, sh = [], 1.0
        for i in range(5):
            if i:
                sh *= 1 - (bb[i] or 0.0) / 100.0
            if ias29 and first and labs[i] < first:
                continue
            idx = cum[min(i + 1, 4)] if ias29 else cum[i]
            if mc[i] and pes[i] and pes[i] > 0:
                pts.append((i, math.log(mc[i] / pes[i] / sh / idx)))
        if len(pts) >= 4:
            mx, my = sum(x for x, _ in pts) / len(pts), sum(y for _, y in pts) / len(pts)
            gh = (math.exp(sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x, _ in pts)) - 1) * 100
    g = max(0.0, min(gs if gh is None else min(gh, gs), P["gCap"]))
    return g, gh, gs, po


def run(cc):
    d = os.path.join(ROOT, "data", cc)
    P = load(os.path.join(ROOT, "pipeline", "params.json"))
    meta = load(os.path.join(d, "meta.json"))
    uni = load(os.path.join(d, "universe.json"))
    hist = load(os.path.join(d, "history.json"), {})
    reports = load(os.path.join(d, "reports.json"), {})
    finarm = load(os.path.join(d, "finarm.json"), {})      # finansman kolu olan sanayi şirketleri (Claude yazar, kaynaklı)
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

    U, L2, F = [], {}, {}
    for u in uni:
        c = u["c"]
        pe, pb = u.get("pe"), u.get("pb")
        roe = (pb / pe * 100.0) if (pe and pb and pe > 0 and pb > 0) else None
        defl = deflate_all or bool(u.get("nom"))
        cf = cpi_of
        # İşlevsel para birimi yabancı olan şirket (meta.flags.fx): özsermaye kârlılığı o para biriminin enflasyonuyla düzeltilir
        # (meta.fx_cpi; kâr da özsermaye de o parayla ölçülür). Enflasyon dizisi yoksa düzeltilmez.
        fxc = ((meta.get("flags") or {}).get("fx") or {}).get(c)
        fxcpi = (meta.get("fx_cpi") or {}).get(fxc["cur"]) if fxc else None
        if fxcpi:
            fys = sorted(y for y in fxcpi if y != "cur")
            cf = lambda lab, t=fxcpi, fys=fys: t["cur"] if lab == "cur" else t[lab] if lab in t else (t["cur"] if lab > fys[-1] else t[fys[0]])
            defl = True
        rr = real(roe, cf("cur")) if defl else roe
        # Kazanç yargısı (CLAUDE.md): son 12 ayın okumaları 2. surun eşiklerinde de yargılanmış kazançla sınanır.
        ej = (reports.get(c) or {}).get("earn") or {}
        ek = ej["k"] if isinstance(ej.get("k"), (int, float)) and 0 < ej["k"] < 1 else 1.0
        e, w = None, None
        if u.get("veh"):
            e, w = 1, "vehicle"
        elif not pe or pe <= 0:
            # kural aynı: pozitif F/K yoksa şirket 1. surda kalır. Yalnız neden doğru adlandırılır:
            # "noprofit" zarar olduğu biliniyor, "nodata" kaynak son 12 ayın kârını vermiyor, "nope" hangisi olduğu bilinmiyor
            e, w = 1, {"loss": "noprofit", "nodata": "nodata"}.get(u.get("np"), "nope")
        elif not pb or pb <= 0:
            # kural aynı: pozitif PD/DD yoksa şirket 1. surda kalır. Yalnız neden doğru adlandırılır:
            # "equity" özsermaye negatif, "nobook" kaynaklarda defter değeri yok (özsermayenin işareti bilinmiyor)
            e, w = 1, ("nobook" if u.get("nb") == "nodata" else "equity")
        elif u["m"] < mcap_min:
            e, w = 1, "small"
        elif rr is None or rr * ek < P["roeMin"]:
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
                rroe6 = [(real(v, cf(lab)) if defl else v) for lab, v in zip(labs, roe6)]
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
                    # eşikler yargılanmış kazançla sınanır: son 12 ay okuması kazanç çarpanıyla alınır (grafikteki rakam kaynağınkidir)
                    valsj = [v * (ek if lab == "cur" else 1.0) for lab, v in zip(labs, rroe6) if v is not None and in_era(lab)]
                    avgj, mnj = sum(valsj) / len(valsj), min(valsj)
                    if mnj < P["eraMin"]:
                        fails.append(dict({"k": "roe_min", "v": round(mnj, 1)}, **({"ej": 1} if mn >= P["eraMin"] else {})))
                    elif avgj < P["eraAvg"]:
                        fails.append(dict({"k": "roe_avg", "v": round(avgj, 1)}, **({"ej": 1} if avg >= P["eraAvg"] else {})))
                elif not fails:
                    fails.append({"k": "history"})
                fin = bool(u.get("fin"))
                nd = h.get("nd")
                fa = None if fin else finarm.get(c)
                ndx = arm_ratio(fa, nd, u.get("per")) if fa else None
                ndt = nd if ndx is None else ndx      # teste giren oran: finansman kolu varsa o hariç; eşik aynı
                if not fin and ndt is not None:
                    hit = {"k": "debt", "v": round(ndt, 2)}
                    if ndx is not None:
                        hit["fa"] = 1                 # sayfa "finansman kolu hariç" diye yazar
                    if ndt > P["ndMax"]:
                        fails.append(hit)
                    elif ndt > P["ndFlag"]:
                        flags.append(hit)
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
                if ek < 1:
                    L2[c]["ek"] = ek               # kazanç yargısı (CLAUDE.md): son 12 ay okumaları bu çarpanla alınır
                roe_c = [x for x in (None if rr is None else rr * ek, rroe6[-2], None if rroe6[-1] is None else rroe6[-1] * ek) if x is not None]
                if roe_c and min(roe_c) > 0:       # 4. surun büyüme hızı (fiyat testi ve ön hesap için)
                    # İşlevsel para birimi yabancı olan şirket (meta.flags.fx) enflasyon muhasebesi uygulamaz: kâr dizisi nominaldir,
                    # her yıl o yılın tüketici enflasyonuyla düzeltilir (CLAUDE.md, "İşlevsel para birimi yabancı olan şirket").
                    fx = bool(fxc)
                    g, gh, gs, gpo = growth(h, labs, cpi_of, min(roe_c), (not defl) and not fx, P,
                                            str(int(min(era_years)) - 1) if (era_explicit and era_years and not fx) else None)
                    L2[c].update(g=rnd(g, 2), gh=rnd(gh, 2), gs=rnd(gs, 2), gpo=rnd(gpo))
                    if fx:
                        L2[c]["fx"] = 1
                    # büyüme yargısı (CLAUDE.md, "Büyüme yargısı"): okuma sırasında bulunan, kaynaklı bir gerçek büyüme hızını aşağı çeker.
                    # Yalnız indirir: formülün verdiği hızın üstüne çıkamaz.
                    gj = (reports.get(c) or {}).get("growth") or {}
                    if isinstance(gj.get("g"), (int, float)) and gj["g"] < g:
                        L2[c].update(gm=rnd(g, 2), g=rnd(max(0.0, gj["g"]), 2), gj=1)
                    if isinstance(gj.get("dy"), (int, float)) and L2[c].get("dy") is None:
                        L2[c].update(dy=gj["dy"], dyj=1)   # kaynakta temettü verimi yok: şirketin kendi belgesinden
                if labs[:5] != years:
                    L2[c]["fy"] = labs[:5]
                if h.get("url"):
                    L2[c]["url"] = h["url"]
                if fa:
                    F[c] = dict(fa, on=1 if ndx is not None else 0)
                    if ndx is not None:
                        L2[c]["ndx"] = F[c]["ndx"] = round(ndx, 2)
                if fails:
                    e, w = 2, fails[0]["k"]
                else:
                    rep = reports.get(c)
                    if not rep or "scores" not in rep:
                        e, w = 3, "pending"          # 2. suru geçti, 3. surda henüz okunmadı
                    elif not l3pass(rep["scores"]):
                        s = rep["scores"]
                        e, w = 3, ("moat" if s["B"] < 2 else "mgmt" if s["D"] < 1 else "fragile")
                    elif (rep.get("growth") or {}).get("permanent"):
                        e, w = 3, "decline"          # kârdaki kötüleşmenin nedeni kalıcı: fiyat testine alınmaz (CLAUDE.md, "Büyüme yargısı")
                    else:
                        e, w = 4, "price"            # kale ya da bekleme: fiyat testi istemcide de hesaplanır
        U.append(dict(c=c, n=u["n"], s=u["s"], p=u["p"], m=u["m"], f=u.get("f"), pe=pe, pb=pb, per=u.get("per"),
                      e=e, w=w, nom=1 if (u.get("nom") or deflate_all or fxcpi) else 0, fin=1 if u.get("fin") else 0,
                      roe=None if roe is None else round(roe, 1), rr=None if rr is None else round(rr, 1)))
        if fxcpi:
            U[-1]["fx"] = fxc["cur"]          # özsermaye kârlılığı bu para biriminin enflasyonuyla düzeltildi
        if ek < 1 and e == 2 and w == "roe_ttm" and rr is not None and rr >= P["roeMin"]:
            U[-1]["ek"] = ek                  # eşiğin altına kazanç yargısıyla indi; sayfa bunu söyler
        if u.get("pc"):
            U[-1]["pc"] = u["pc"]             # fiyatı ülkenin olağan biriminden farklı yazılan pay
        if u.get("pbs"):
            U[-1]["pbs"] = u["pbs"]           # PD/DD, kaynağın PD/DD alanından değil: aynı kaynağın başka alanı, ikinci kaynak ya da yıllık bilanço
        if u.get("pes"):
            U[-1]["pes"] = u["pes"]           # F/K, kaynağın başka bir son 12 ay alanından hesaplandı ("eps" ya da "roe")

    R = {c: r for c, r in reports.items() if c in L2 and L2[c]["ok"]}
    # raporu yazılmış, sonra 1. ya da 2. surda elenmiş şirketler: rapor silinmez, sayfada "güncellenmiyor" uyarısıyla görünür
    codes = set(u["c"] for u in U)
    RX = {c: r for c, r in reports.items() if c not in R and c in codes and r.get("scores")}
    # elenen şirketin beş yıllık rakamlarının altında görünen kısa not
    N = {c: r["note"] for c, r in reports.items() if c not in R and r.get("note")}
    out = dict(cc=cc, asof=meta["asof"], U=U, L2=L2, R=R, RX=RX, N=N, F=F)
    json.dump(out, open(os.path.join(d, "core.json"), "w", encoding="utf-8"), ensure_ascii=False)

    cnt = collections.Counter((u["e"], u["w"]) for u in U)
    print(cc, "evren", len(U), "| 1. suru geçen", sum(1 for u in U if u["e"] > 1), "| 2. suru geçen", sum(1 for u in U if u["e"] > 2),
          "| sırada", cnt.get((3, "pending"), 0), "| 3. suru geçen", sum(1 for u in U if u["e"] > 3))
    print("  ", dict(sorted(cnt.items(), key=lambda kv: (kv[0][0], -kv[1]))))
    for c, f in sorted(F.items()):
        print(f"   finansman kolu: {c:8} {f.get('arm', '')[:30]:30} " + (f"kaynağın oranı {L2[c]['nd']} -> kol hariç {f['ndx']}" if f["on"] else
              f"DÜZELTME UYGULANMADI (kayıt {f.get('per')}, evren {next(u['per'] for u in U if u['c'] == c)}): yeni dönemin rakamlarını oku"))
    if RX:
        print("   raporu saklanan, şimdi 1. ya da 2. surda elenenler:", ", ".join(sorted(RX)))
    # fiyat testi (istemcideki val() ile aynı formül)
    by = {u["c"]: u for u in U}
    for c, u in sorted(by.items()):
        if u["e"] != 4:
            continue
        l, s = L2[c], R[c]["scores"]
        t = price_test(P, u, l, s["B"] >= 3)
        roe_n, pen, fair, mos = t["roe_n"], t["pen"], t["fair"], t["mos"]
        print(f"   {c:8} temkinli ROE {roe_n:5.1f} | büyüme {l.get('g')} (geçmiş {l.get('gh')}, sürdürülebilir {l.get('gs')}) | temkinli F/K {pen:5.1f} | "
              f"adil İNA {t['dcf']:4.1f} PEG {t['peg']:4.1f} | marj {mos:6.1f}% | "
              f"alım eşiği {u['p'] * fair * (1 - P['mos'] / 100) / pen:9.2f} | fiyat {u['p']} -> {'KALE' if mos >= P['mos'] else 'BEKLEME'}")
    return out


if __name__ == "__main__":
    for cc in sys.argv[1:] or ["TR"]:
        run(cc)
