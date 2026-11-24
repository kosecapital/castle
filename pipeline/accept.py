#!/usr/bin/env python3
"""Gelen veriyi (data/TR/in/) denetler, yerine alır, süzgeci çalıştırır ve öncekiyle karşılaştırır (genç Buffett yöntemi).

  python3 pipeline/accept.py --list        # yeni veri bekliyor mu
  python3 pipeline/accept.py TR --dry      # yalnız denetle ve farkı göster; hiçbir dosyayı değiştirme
  python3 pipeline/accept.py TR            # denetle, yerine al, süzgeci çalıştır
  python3 pipeline/accept.py TR --read     # okuma listesi: mercekten geçen ve henüz okunmamış (kırmızı bayrak bakılmamış) şirketler

İnternet kullanmaz. Bir denetim tutmazsa hiçbir şeyi değiştirmez ve 1 koduyla çıkar (CLAUDE.md kural 6).
Denetimler:
  1. Toplayıcı hatasız bitmiş mi; şirket sayısı öncekinin %15 içinde mi; F/K dolu olanların oranı makul mü (%30-%90).
  2. Mali tablolar: bilanço beklenen şirketlerin en az %60'ında var mı; birim tutarlı mı (ana ortaklık özsermayesi ≈ piyasa değeri ÷ PD/DD,
     şirketlerin ortancasında %15 içinde).
  3. Süzgeçten sonra: hangi şirket merceğe girdi, hangisi çıktı.
"""
import json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "pipeline"))
import funnel  # noqa: E402

J = lambda *p: os.path.join(ROOT, *p)
load = lambda p, d=None: json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d


def lenses(core):
    return {u["c"]: set(u["L"]) for u in core["U"]} if core else {}


def listing():
    st = load(J("data", "TR", "in", "status.json"), {})
    meta = load(J("data", "TR", "meta.json"), {})
    fin = st.get("fin", {})
    wait = (st.get("fetched") or "")[:10] > (meta.get("accepted") or "")
    print(f'TR  {"yenileme bekliyor" if wait else "güncel"} | veri {st.get("fetched", "-")[:16]} | yayındaki {meta.get("accepted", "-")} (fiyat {meta.get("asof")}) '
          f'| şirket {st.get("kept")} | mali tablo {fin.get("have", "-")} (eksik {fin.get("failed_n", "-")}) | {"tamam" if st.get("ok") else "HATA: " + "; ".join(st.get("errors", []))[:120]}')


def check(cc):
    d, i = J("data", cc), J("data", cc, "in")
    st, uni_new = load(os.path.join(i, "status.json"), {}), load(os.path.join(i, "universe.json"))
    uni_old = load(os.path.join(d, "universe.json"), [])
    bad = []
    if not st.get("ok"):
        bad.append("toplayıcı hatalı bitti: " + "; ".join(st.get("errors", []))[:300])
    if not uni_new:
        bad.append("gelen evren boş")
        return bad, st
    if uni_old and abs(len(uni_new) - len(uni_old)) > 0.15 * len(uni_old):
        bad.append(f"şirket sayısı %15'ten çok değişti: {len(uni_old)} -> {len(uni_new)}")
    pe = sum(1 for u in uni_new if u.get("pe")) / len(uni_new)
    if not 0.30 <= pe <= 0.90:
        bad.append(f"F/K dolu oranı %{100 * pe:.0f} (beklenen %30-%90)")
    fin = load(os.path.join(i, "fin.json"))
    if fin is not None:
        want = sum(1 for u in uni_new if u.get("s") not in funnel.NO_SHEET)
        have = sum(1 for u in uni_new if u["c"] in fin and fin[u["c"]].get("per") == u.get("per"))
        if have < 0.6 * want:
            bad.append(f"mali tablo yalnız {have}/{want} şirkette (bu dönem için)")
        unit, chk = funnel.fin_unit(uni_new, fin)
        if unit is None or chk is None or abs(chk - 1) > 0.15:
            bad.append(f"mali tabloların birimi tutarsız (birim {unit}, ortanca oran {chk}): kalem eşleşmesini denetle (status.json içindeki fin_sample)")
    return bad, st


def accept(cc, dry=False):
    d, i = J("data", cc), J("data", cc, "in")
    bad, st = check(cc)
    for b in bad:
        print("DENETİM TUTMADI:", b)
    if bad:
        print("Hiçbir dosya değiştirilmedi. Yayımlama; nedeni çalıştırma özetine yaz.")
        sys.exit(1)
    old = load(os.path.join(d, "core.json"))
    keep = {f: open(os.path.join(d, f), "rb").read() for f in ("universe.json", "fin.json", "meta.json", "core.json") if os.path.exists(os.path.join(d, f))}
    try:
        shutil.copyfile(os.path.join(i, "universe.json"), os.path.join(d, "universe.json"))
        if os.path.exists(os.path.join(i, "fin.json")):
            shutil.copyfile(os.path.join(i, "fin.json"), os.path.join(d, "fin.json"))
        meta, mac = load(os.path.join(d, "meta.json")), load(os.path.join(i, "macro.json"), {})
        meta["asof"] = st.get("price_date") or meta.get("asof")
        meta["accepted"] = (st.get("fetched") or "")[:10]
        if mac.get("fx"):
            meta["fx"] = mac["fx"]
        if mac.get("cpi_cur") is not None:
            meta.setdefault("cpi", {})["cur"] = mac["cpi_cur"]
        if mac.get("rates"):
            meta["rates_in"] = mac["rates"]                 # toplayıcının getirdiği faiz; meta.rates (kaynaklı, elle) önce gelir
        json.dump(meta, open(os.path.join(d, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        core = funnel.run(cc)
        funnel.summary(core)
        a, b = lenses(old), lenses(core)
        ins = sorted(c for c in b if b[c] - a.get(c, set()))
        outs = sorted(c for c in a if a[c] - b.get(c, set()))
        by = {u["c"]: u for u in core["U"]}
        if ins:
            print("merceğe girenler: " + ", ".join(f'{c} ({",".join(sorted(b[c] - a.get(c, set())))})' for c in ins))
        if outs:
            print("mercekten çıkanlar: " + ", ".join(f'{c} ({",".join(sorted(a[c] - b.get(c, set())))})' for c in outs))
        stale = [c for c, w in load(os.path.join(d, "special.json"), {}).items() if w.get("status") in ("active", "pending")]
        if stale:
            print("özel durum kayıtları (KAP'tan durumu yeniden bak): " + ", ".join(stale))
    finally:
        if dry:
            for f, b in keep.items():
                open(os.path.join(d, f), "wb").write(b)
            if "fin.json" not in keep and os.path.exists(os.path.join(d, "fin.json")):
                os.remove(os.path.join(d, "fin.json"))
            print("(deneme: dosyalar eski haline döndürüldü)")


def reading(cc, limit=30):
    """Okuma listesi: mercekten geçen, kırmızı bayrağı henüz bakılmamış şirketler (önce birden çok mercekten geçen, sonra büyükler)."""
    core = load(J("data", cc, "core.json"))
    seen = load(J("data", cc, "flags.json"), {})
    checked = set(load(J("data", cc, "checked.json"), {}).keys())
    rows = [u for u in core["U"] if u["L"] and u["c"] not in seen and u["c"] not in checked]
    rows.sort(key=lambda u: (-len(u["L"]), -u["m"]))
    print(f"okunacak: {len(rows)} şirket (mercekten geçen, kırmızı bayrağa bakılmamış)")
    for u in rows[:limit]:
        print(f'  {u["c"]:7} {u["n"][:32]:32} {",".join(u["L"]):10} PD {u["m"]:>10,.0f} mn | F/K {u.get("pe")} | kâr verimi {u.get("ey")}' + ("  ! F/K 2,5 altı" if u.get("eyw") else ""))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "--list":
        listing()
    elif "--read" in a:
        reading(a[0].upper())
    else:
        accept(a[0].upper(), dry="--dry" in a)
