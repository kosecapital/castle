#!/usr/bin/env python3
"""Gelen veriyi (data/<CC>/in/) denetler, yerine alır, süzgeci çalıştırır ve öncekiyle karşılaştırır.

  python3 pipeline/accept.py --list        # hangi ülkede yeni veri bekliyor
  python3 pipeline/accept.py TR --dry      # yalnız denetle ve farkı göster; hiçbir dosyayı değiştirme
  python3 pipeline/accept.py TR            # denetle, yerine al, süzgeci çalıştır
  python3 pipeline/accept.py US --queue    # sırada bekleyenlerin okuma sırası (hiçbir şeyi değiştirmez)
  python3 pipeline/accept.py US --debt     # yalnız borç testinden elenenler ve finansman kolu kayıtları (hiçbir şeyi değiştirmez)

İnternet kullanmaz. Bir denetim tutmazsa hiçbir şeyi değiştirmez ve 1 koduyla çıkar (CLAUDE.md kural 6: emin değilsen yayımlama).
Denetimler:
  1. Toplayıcı hatasız bitmiş mi; şirket sayısı öncekinin %15 içinde mi; F/K dolu olanların oranı %30-90 arasında mı;
     kârlı ve yeterince büyük şirketlerin en çok %10'unda PD/DD eksik mi.
  2. Adayların en çok %30'unun beş yıllık verisi eksik mi (daha fazlası adres kalıbı hatasıdır: pipeline/sources.json).
  3. Süzgeçten sonra: 2. suru geçenlerin en az %70'i aynı mı (önceki sonuç varsa).
"""
import json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import funnel  # noqa: E402

J = lambda *p: os.path.join(ROOT, *p)


def load(path, default=None):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else default


def kales(core, P):
    """build_site.py ve sayfadaki val() ile aynı hesap."""
    out = {}
    for u in core["U"]:
        if u["e"] != 4:
            continue
        l, s = core["L2"][u["c"]], core["R"][u["c"]]["scores"]
        t = funnel.price_test(P, u, l, s["B"] >= 3, s)
        out[u["c"]] = (round(t["mos"], 1), t["kale"])
    return out


def state(core, P):
    """Şirket kodu -> okunur durum."""
    if not core:
        return {}
    mos, out = kales(core, P), {}
    for u in core["U"]:
        if u["e"] == 4:
            out[u["c"]] = ("kale" if mos[u["c"]][1] else "kapıda") + f" (marj %{mos[u['c']][0]:.0f})"
        elif u["e"] == 3:
            out[u["c"]] = "sırada" if u["w"] == "pending" else "3. surda elendi: " + u["w"]
        else:
            out[u["c"]] = f"{u['e']}. surda elendi: {u['w']}"
    return out


def queue(cc, core=None, limit=40):
    """Sırada bekleyenlerin okuma sırası: önce fiyatı kale olmaya yetenler (dar hendekle, sonra geniş hendekle), sonra en büyükler."""
    P = load(J("pipeline", "params.json"))
    core = core or load(J("data", cc, "core.json"))
    rows = []
    for u in core["U"]:
        if not (u["e"] == 3 and u["w"] == "pending"):
            continue
        l = core["L2"][u["c"]]
        mn, mw = funnel.price_test(P, u, l, False)["mos"], funnel.price_test(P, u, l, True)["mos"]
        rows.append((0 if mn >= P["mos"] else 1 if mw >= P["mos"] else 2, -u["m"], u["c"], u["n"], u["s"], u["m"], mn, mw, u.get("per")))
    rows.sort()
    n0, n1 = sum(1 for r in rows if r[0] == 0), sum(1 for r in rows if r[0] == 1)
    print(f"okuma sırası: {len(rows)} şirket sırada | dar hendekle bile kale olabilecek {n0} | yalnız geniş hendekle kale olabilecek {n1}")
    for r in rows[:limit]:
        print(f"  {'A' if r[0] == 0 else 'B' if r[0] == 1 else 'C'}  {r[2]:9} {r[3][:34]:34} {r[4][:22]:22} PD {r[5]:>12,.0f} mn | marj dar %{r[6]:5.0f} geniş %{r[7]:5.0f} | {r[8]}")
    if len(rows) > limit:
        print(f"  ... ve {len(rows) - limit} şirket daha (tamamı: --queue --all)")
    return rows


def debt_review(cc, core=None, limit=40):
    """Finansman kolu düzeltmesinin durumu ve yalnız borç testinden elenen şirketler (CLAUDE.md, "Finansman kolu").

    Düzeltmenin kendisi funnel.py içindedir; burada yalnız bakılacak şirketler listelenir. Hiçbir şeyi değiştirmez."""
    core = core or load(J("data", cc, "core.json"))
    recs, F = load(J("data", cc, "finarm.json"), {}), core.get("F", {})
    byc = {u["c"]: u for u in core["U"]}
    on = [c for c in sorted(F) if F[c].get("on")]
    off = [c for c in sorted(F) if not F[c].get("on")]
    if on:
        print("finansman kolu hariç hesaplananlar: " + ", ".join(f"{c} ({core['L2'][c]['nd']} -> {F[c]['ndx']})" for c in on))
    if off:
        print("FİNANSMAN KOLU RAKAMI ESKİDİ, düzeltme uygulanmadı: " + ", ".join(f"{c} (kayıt {F[c].get('per')}, evren {byc[c].get('per')})" for c in off))
        print("  -> yeni bilanço döneminin rakamlarını oku, data/" + cc + "/finarm.json içine yaz, funnel.py'yi yeniden çalıştır. Rakam bulunamazsa kayda dokunma: sayfa konsolide oranı kullanır ve bunu söyler.")
    none = set(recs.get("_none", []))                     # bakıldı: içinde tam konsolide finansman şirketi yok
    gone = [c for c in sorted(recs) if c not in F and not c.startswith("_")]
    if gone:
        print("finansman kolu kaydı olup 2. sura gelmeyenler (bilgi): " + ", ".join(gone))
    only = sorted((-byc[c]["m"], c) for c, l in core["L2"].items() if not l["ok"] and [f["k"] for f in l["fails"]] == ["debt"] and c not in recs and c not in none)
    if only:
        print(f"yalnız borç testinden elenen, henüz bakılmamış {len(only)} şirket. İçinde tam konsolide bir finansman şirketi olan varsa finansman kolu kuralı uygulanır; yoksa kodu finarm.json içindeki _none listesine yaz:")
        for _, c in only[:limit]:
            u = byc[c]
            print(f"  {c:9} {u['n'][:34]:34} {u['s'][:22]:22} net borç/FAVÖK {core['L2'][c]['nd']:<5} | {u.get('per')}")
        if len(only) > limit:
            print(f"  ... ve {len(only) - limit} şirket daha")
    if not (off or only):
        print("borç testinde bakılacak yeni şirket yok.")


def listing():
    rows = []
    for cc in sorted(os.listdir(J("data"))):
        st = load(J("data", cc, "in", "status.json"))
        if not st:
            continue
        meta = load(J("data", cc, "meta.json"))
        asof = (meta or {}).get("asof")
        new = not os.path.exists(J("data", cc, "core.json"))
        waiting = new or not asof or st["fetched"][:10] > asof
        h = st.get("history", {})
        rows.append((cc, "YENİ ÜLKE" if new else "yenileme bekliyor" if waiting else "güncel", st["fetched"][:16], asof or "-", st.get("kept"),
                     h.get("candidates"), h.get("failed_n"), "tamam" if st.get("ok") else "HATA: " + "; ".join(st.get("errors", []))[:80]))
    print(f"{'ülke':5} {'durum':18} {'veri':17} {'yayındaki':11} {'şirket':>7} {'aday':>5} {'eksik':>5}  toplayıcı")
    for r in rows:
        print(f"{r[0]:5} {r[1]:18} {r[2]:17} {r[3]:11} {str(r[4]):>7} {str(r[5]):>5} {str(r[6]):>5}  {r[7]}")
    if not rows:
        print("gelen veri yok")


def accept(cc, dry=False):
    d, P = J("data", cc), load(J("pipeline", "params.json"))
    st, uni, mac = load(os.path.join(d, "in", "status.json")), load(os.path.join(d, "in", "universe.json")), load(os.path.join(d, "in", "macro.json"), {})
    hin = load(os.path.join(d, "in", "history.json"), {})
    bad = []
    if not st or not uni:
        raise SystemExit(f"{cc}: gelen veri yok (data/{cc}/in/). Toplayıcı her gece GitHub'da çalışır.")
    if not st.get("ok"):
        bad.append("toplayıcı hatayla bitti: " + "; ".join(st.get("errors", [])))
    meta = load(os.path.join(d, "meta.json"))
    if not meta:
        print(f"{cc}: meta.json yok. Önce onu yaz (CLAUDE.md, İş A). Toplayıcının önerdiği değerler:")
        print(json.dumps({k: mac.get(k) for k in ("cur", "pcur", "fx", "mcapMin", "years", "cpi", "cpi_cur", "cpi_src", "cpi_cur_src")}, ensure_ascii=False, indent=1))
        print("ilk beş şirket (ikinci kaynakla karşılaştır):", json.dumps(st.get("top5"), ensure_ascii=False))
        raise SystemExit(2)
    old_uni, old_core = load(os.path.join(d, "universe.json")), load(os.path.join(d, "core.json"))
    n = len(uni)
    if old_uni and abs(n / len(old_uni) - 1) > 0.15:
        bad.append(f"şirket sayısı {len(old_uni)} -> {n}: %15'ten fazla değişti")
    pef = 100 * sum(1 for u in uni if u.get("pe")) / max(1, n)
    if not 30 <= pef <= 90:
        bad.append(f"F/K dolu olanların oranı %{pef:.0f}: olağan aralığın (%30-90) dışında")
    # PD/DD: kârlı ve yeterince büyük şirketlerde defter değeri bilinmeyenlerin oranı (özsermayesi negatif olduğu bilinenler sayılmaz)
    core1 = [u for u in uni if not u.get("veh") and u.get("pe") and u["pe"] > 0 and u["m"] >= meta.get("mcapMin", 0)]
    nob = [u for u in core1 if u.get("pb") is None and u.get("nb") != "neg"]
    if core1 and len(nob) / len(core1) > 0.10:
        big = ", ".join(u["c"] for u in sorted(nob, key=lambda u: -u["m"])[:6])
        bad.append(f"kârlı şirketlerin %{100 * len(nob) / len(core1):.0f} kadarında PD/DD yok ({len(nob)}/{len(core1)}; en büyükleri {big}): bunlar yanlış nedenle 1. surda kalırdı. status.json içindeki pb_fix'e bak")
    h = st.get("history", {})
    cand, have = h.get("candidates") or 0, sum(1 for c in hin if hin[c])
    if cand and (cand - have) / cand > 0.30:
        bad.append(f"adayların %{100 * (cand - have) / cand:.0f} kadarının beş yıllık verisi eksik ({cand - have}/{cand}); adres kalıbını denetle (pipeline/sources.json)")
    if h.get("blocked"):
        print("  not: oran sayfası kaynağı istekleri sınırladı; eksikler sonraki gece tamamlanır.")
    if bad:
        print(f"{cc}: DENETİM TUTMADI, hiçbir şey değiştirilmedi:")
        for b in bad:
            print("  -", b)
        raise SystemExit(1)

    # yerine al (önce yedek)
    files = ["universe.json", "history.json", "meta.json", "core.json"]
    backup = {f: open(os.path.join(d, f), encoding="utf-8").read() if os.path.exists(os.path.join(d, f)) else None for f in files}
    hist = load(os.path.join(d, "history.json"), {})
    hist.update({c: v for c, v in hin.items() if v})
    meta["asof"] = st.get("price_date") or st["fetched"][:10]
    if mac.get("fx"):
        meta["fx"] = mac["fx"]
    if mac.get("cpi_cur") is not None:
        meta.setdefault("cpi", {})["cur"] = mac["cpi_cur"]
    if st.get("pcur") and st.get("pcur") != st.get("cur"):
        meta["pcur"] = st["pcur"]
    if old_uni and "--names" not in sys.argv:              # bilinen şirketin adı korunur (kaynak adları kısaltmalı gelebiliyor)
        names = {u["c"]: u["n"] for u in old_uni}
        for u in uni:
            u["n"] = names.get(u["c"], u["n"])
    json.dump(uni, open(os.path.join(d, "universe.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(hist, open(os.path.join(d, "history.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    json.dump(meta, open(os.path.join(d, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    def restore():
        for f, txt in backup.items():
            p = os.path.join(d, f)
            if txt is None:
                if os.path.exists(p):
                    os.remove(p)
            else:
                open(p, "w", encoding="utf-8").write(txt)

    try:
        new_core = funnel.run(cc)
    except BaseException:
        restore(); raise
    a, b = state(old_core, P), state(new_core, P)
    if old_core:
        was = set(u["c"] for u in old_core["U"] if u["e"] >= 3)
        now = set(u["c"] for u in new_core["U"] if u["e"] >= 3)
        if len(was) >= 5 and len(was & now) / len(was) < 0.70:
            restore()
            print(f"{cc}: DENETİM TUTMADI: 2. suru geçenlerin yalnız %{100 * len(was & now) / len(was):.0f} kadarı aynı kaldı (eşik %70). Veri hatası olabilir; hiçbir şey değiştirilmedi.")
            print("  çıkanlar:", ", ".join(f"{c} ({b.get(c, 'evrende yok')})" for c in sorted(was - now)))
            raise SystemExit(1)
    # özet
    print(f"\n{cc}: veri {meta['asof']} | kaynak: {st.get('source')}")
    key = lambda c: c in a and a[c] != b.get(c) and (a[c][:4] in ("kale", "kapı", "sıra", "3. s") or b.get(c, "")[:4] in ("kale", "kapı", "sıra", "3. s"))
    ch = [c for c in sorted(set(a) | set(b)) if key(c) or (c not in a and b[c][:4] in ("kale", "kapı", "sıra", "3. s"))]
    if old_core:
        print("durumu değişenler (2. suru geçenler arasında):" if ch else "2. suru geçenler arasında durumu değişen yok.")
        for c in ch:
            print(f"  {c:8} {a.get(c, 'evrende yoktu'):34} -> {b.get(c, 'evrenden çıktı')}")
    reports = load(os.path.join(d, "reports.json"), {})
    byc = {u["c"]: u for u in new_core["U"]}
    old_per = lambda c: reports[c].get("per") and reports[c]["per"] != byc[c].get("per")
    stale = [c for c in reports if c in byc and byc[c]["e"] == 4 and old_per(c)]
    stale3 = [c for c in reports if c in byc and byc[c]["e"] == 3 and byc[c]["w"] != "pending" and old_per(c)]
    pend = [u["c"] for u in new_core["U"] if u["e"] == 3 and u["w"] == "pending"]
    print("yeni bilançosu gelen, raporu güncellenecekler (kale ve kapıda bekleyenler):", ", ".join(stale) or "-")
    if stale3:
        print(f"3. surda elenmiş {len(stale3)} şirketin de yeni bilançosu var; elenme nedeni değişmiş olabilecekleri hak kalırsa yeniden oku:", ", ".join(stale3[:30]))
    gone = sorted(new_core.get("RX", {}))
    if gone:
        print("raporu saklanan, şimdi 1. ya da 2. surda elenenler (sayfada uyarıyla görünür; `one` cümlesi yeni duruma uymalı):", ", ".join(gone))
    nog = [u["c"] for u in new_core["U"] if u["e"] == 4 and not (reports.get(u["c"]) or {}).get("growth")]
    oldg = [u["c"] for u in new_core["U"] if u["e"] == 4 and (reports.get(u["c"]) or {}).get("growth") and reports[u["c"]]["growth"].get("per") != u.get("per")]
    noe = [u["c"] for u in new_core["U"] if u["e"] == 4 and not (reports.get(u["c"]) or {}).get("earn")]
    if noe:
        print("KAZANÇ YARGISI EKSİK (4. surdaki her şirkette zorunlu; CLAUDE.md, \"Kazanç yargısı\"):", ", ".join(noe))
    if nog:
        print("BÜYÜME YARGISI EKSİK (4. surdaki her şirkette zorunlu; CLAUDE.md, \"Büyüme yargısı\"):", ", ".join(nog))
    if oldg:
        print("büyüme yargısı eski bilanço dönemine ait, güncel gerçeklerle yeniden yazılacaklar:", ", ".join(oldg))
    if pend:
        queue(cc, new_core, 30)
    else:
        print("sırada bekleyen şirket yok.")
    debt_review(cc, new_core, 15)
    if dry:
        restore(); print("(deneme: dosyalar eski haline döndürüldü)")
    else:
        print("yerine alındı. Sırada: raporlar, `node pipeline/geo.mjs " + cc + "`, `python3 pipeline/build_site.py`.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "--list" in args:
        listing()
    elif "--queue" in args:
        for cc in [a for a in args if not a.startswith("--")]:
            queue(cc.upper(), limit=100000 if "--all" in args else 60)
    elif "--debt" in args:
        for cc in [a for a in args if not a.startswith("--")]:
            print(cc.upper() + ":"); debt_review(cc.upper(), limit=100000 if "--all" in args else 40)
    else:
        for cc in [a for a in args if not a.startswith("--")]:
            accept(cc.upper(), dry="--dry" in args)
