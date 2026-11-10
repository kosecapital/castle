#!/usr/bin/env python3
"""Castle sitesini derler.

Girdi : data/<CC>/{meta,core,geo}.json (önce funnel.py ve geo.mjs çalışmış olmalı), pipeline/*.json, pipeline/template.html
Çıktı : docs/index.html, docs/data/<CC>.json, docs/data/world50.json   -> GitHub Pages bu klasörü yayımlar
        .preview/index.html (kitaplıklar dosyanın içinde; yerel deneme için)

Kullanım: python3 pipeline/build_site.py
"""
import json, os, shutil, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
load = lambda p: json.load(open(p, encoding="utf-8"))
dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))

P = load(J("pipeline", "params.json"))
CH = load(J("pipeline", "charter.json"))
ORDER = load(J("pipeline", "countries.json"))["countries"]
SITE = load(J("pipeline", "site.json")) if os.path.exists(J("pipeline", "site.json")) else {}
COLS = ["c", "n", "s", "p", "m", "f", "pe", "pb", "per", "e", "w", "nom", "fin", "roe", "rr", "x", "y", "a"]
META_KEYS = ["cc", "iso", "name", "exchange", "cur", "asof", "fx", "years", "era", "era_label", "cpi", "small_text", "small_rule",
             "inflation_note", "data_notes", "chart_note", "chart_note_nominal"]


def kale_list(core):
    """İstemcideki val() ile aynı hesap: varsayılan eşiklerle kaleye girenler."""
    out = []
    for u in core["U"]:
        if u["e"] != 4:
            continue
        l, s = core["L2"][u["c"]], core["R"][u["c"]]["scores"]
        cand = [x for x in (u["rr"] if u["nom"] else u["roe"], l["rroe"][-2], l["rroe"][-1]) if x is not None]
        pen = u["pb"] / (min(cand) / 100.0)
        fair = 100.0 / (P["r"] - (P["gWide"] if s["B"] >= 3 else P["gNarrow"]))
        if (1 - pen / fair) * 100 >= P["mos"]:
            out.append(u["c"])
    return out


def country(cc):
    d = J("data", cc)
    meta, core, geo = load(os.path.join(d, "meta.json")), load(os.path.join(d, "core.json")), load(os.path.join(d, "geo.json"))
    sectors, whys, pers = [], [], []
    ix = lambda lst, v: lst.index(v) if v in lst else (lst.append(v) or len(lst) - 1)
    rows = []
    for u in core["U"]:
        x, y = geo["pos"][u["c"]]
        rows.append([u["c"], u["n"], ix(sectors, u["s"]), u["p"], u["m"], u.get("f"), u["pe"], u["pb"], ix(pers, u.get("per")), u["e"],
                     ix(whys, u["w"]), u["nom"], u["fin"], u["roe"], u["rr"], x, y, geo["ang"].get(u["c"])])
    m = {k: meta[k] for k in META_KEYS if k in meta}
    doc = dict(v=1, cc=cc, meta=m, W=geo["W"], sectors=sectors, whys=whys, pers=pers, cols=COLS, rows=rows, L2=core["L2"], R=core["R"])
    kl = kale_list(core)
    U = core["U"]
    idx = dict(cc=cc, iso=meta["iso"], name=meta["name"], cur=meta["cur"], asof=meta["asof"], n=len(U),
               p1=sum(1 for u in U if u["e"] > 1), p2=sum(1 for u in U if u["e"] > 2), p3=sum(1 for u in U if u["e"] > 3),
               pend=sum(1 for u in U if u["e"] == 3 and u["w"] == "pending"), kale=len(kl), kales=kl, fit=geo["W"]["fit"], c=geo["W"]["c"])
    return doc, idx


def main():
    os.makedirs(J("docs", "data"), exist_ok=True)
    done = [k for k in ORDER if os.path.exists(J("data", k["cc"], "core.json")) and os.path.exists(J("data", k["cc"], "geo.json"))]
    # taranan ülkeler: en yeni eklenen en üstte değil, borsa büyüklüğüne göre; ilk açılışta odak ilk sıradaki olur
    countries = []
    for k in done:
        doc, idx = country(k["cc"])
        open(J("docs", "data", k["cc"] + ".json"), "w", encoding="utf-8").write(dump(doc))
        countries.append(idx)
    focus = SITE.get("focus")
    if focus:
        countries.sort(key=lambda c: 0 if c["cc"] == focus else 1)
    queue = [dict(cc=k["cc"], iso=k["iso"], name=k["name"]) for k in ORDER if k not in done and not k.get("hold")]
    index = dict(built=datetime.date.today().isoformat(), P=P, CH=CH, countries=countries, queue=queue, cadence=SITE.get("cadence"))
    nm = J("pipeline", "node_modules")
    world110 = open(os.path.join(nm, "world-atlas", "countries-110m.json"), encoding="utf-8").read()
    shutil.copyfile(os.path.join(nm, "world-atlas", "countries-50m.json"), J("docs", "data", "world50.json"))
    open(J("docs", ".nojekyll"), "w").write("")

    tpl = open(J("pipeline", "template.html"), encoding="utf-8").read()
    for ph in ("/*__INDEX__*/", "/*__WORLD__*/", "<!--__LIBS__-->", "<!--__INLINE__-->"):
        assert tpl.count(ph) == 1, ph
    safe = lambda s: s.replace("<", "\\u003c")
    body = tpl.replace("/*__INDEX__*/", safe(dump(index))).replace("/*__WORLD__*/", safe(world110))
    cdn = ('<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>\n'
           '<script src="https://cdnjs.cloudflare.com/ajax/libs/topojson/3.0.2/topojson.min.js"></script>')
    head = ('<!doctype html><html lang="tr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="description" content="Castle: bir ülkedeki bütün hisseleri Buffett ve Munger ilkeleriyle dört surdan geçiren değer yatırımı atlası.">'
            '<style>:root{color-scheme:light;padding:env(safe-area-inset-top,0px) 0 env(safe-area-inset-bottom,0px)}'
            'body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>'
            '</head><body>')
    # 1) site: tam HTML belgesi (GitHub Pages ve Wix içine gömme için)
    open(J("docs", "index.html"), "w", encoding="utf-8").write(head + body.replace("<!--__LIBS__-->", cdn).replace("<!--__INLINE__-->", "") + "</body></html>")
    # 2) Claude sayfası: iskeletsiz gövde (yayın aracı iskeleti kendisi ekler)
    os.makedirs(J("dist"), exist_ok=True)
    #    odak ülke ve ayrıntılı harita sayfaya gömülür: Claude sayfası dosya yüklemeye bağlı kalmadan açılır; diğer ülkeler yanındaki dosyalardan okunur
    first = countries[0]["cc"] if countries else None
    bundle = {"data/world50.json": json.load(open(J("docs", "data", "world50.json"), encoding="utf-8"))}
    if first:
        bundle["data/" + first + ".json"] = json.load(open(J("docs", "data", first + ".json"), encoding="utf-8"))
    inline = '<script type="application/json" id="castle-inline">' + safe(dump(bundle)) + "</script>"
    open(J("dist", "castle.html"), "w", encoding="utf-8").write(body.replace("<!--__LIBS__-->", cdn).replace("<!--__INLINE__-->", inline))
    # 3) yerel deneme: kitaplıklar gömülü
    if os.path.exists(os.path.join(nm, "d3", "dist", "d3.min.js")):
        d3 = open(os.path.join(nm, "d3", "dist", "d3.min.js"), encoding="utf-8").read()
        tj = open(os.path.join(nm, "topojson-client", "dist", "topojson-client.min.js"), encoding="utf-8").read()
        os.makedirs(J(".preview"), exist_ok=True)
        libs = "<script>" + d3 + "</script>\n<script>" + tj + "</script>"
        open(J(".preview", "index.html"), "w", encoding="utf-8").write(head + body.replace("<!--__LIBS__-->", libs).replace("<!--__INLINE__-->", "") + "</body></html>")
        open(J(".preview", "artifact.html"), "w", encoding="utf-8").write(head + body.replace("<!--__LIBS__-->", libs).replace("<!--__INLINE__-->", inline) + "</body></html>")
        link = J(".preview", "data")
        if not os.path.exists(link):
            os.symlink(J("docs", "data"), link)
    print("taranan:", ", ".join(f'{c["cc"]} ({c["n"]} şirket, {c["kale"]} kale: {" ".join(c["kales"]) or "-"})' for c in countries) or "-")
    print("sırada:", len(queue), "ülke; ilk beş:", ", ".join(q["name"] for q in queue[:5]))
    for f in ["docs/index.html", "dist/castle.html"] + ["docs/data/" + x for x in sorted(os.listdir(J("docs", "data")))]:
        print(f"  {f:28} {os.path.getsize(J(*f.split('/'))):>9,} bayt")


if __name__ == "__main__":
    main()
