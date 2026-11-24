#!/usr/bin/env python3
"""Castle sitesini derler (genç Buffett yöntemi, yalnız Türkiye; Alper'in 24 Kasım 2026 kararı).

Girdi : data/TR/{meta,core}.json (önce funnel.py çalışmış olmalı), pipeline/params.json, pipeline/site.json, pipeline/template.html
Çıktı : docs/index.html (veri gömülü), docs/data/TR.json, docs/data/summary.json  -> GitHub Pages bu klasörü yayımlar
        dist/castle.html (Claude sayfası; iskeletsiz gövde), .preview/index.html (yerel deneme)

Kullanım: python3 pipeline/build_site.py
"""
import json, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = lambda *p: os.path.join(ROOT, *p)
load = lambda p: json.load(open(p, encoding="utf-8"))
dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
SITE = load(J("pipeline", "site.json")) if os.path.exists(J("pipeline", "site.json")) else {}
CC = "TR"

# Arama ve paylaşım (Alper'in 15 Kasım 2026 onayıyla): başlık seçilen dile döner; her dil adresi kendini asıl sayfa gösterir.
SITE_URL = "https://www.kosecapital.com/castle/"
TITLE = {"tr": "Castle · Borsa İstanbul değer taraması · Kose Capital", "en": "Castle · Borsa İstanbul value screen · Kose Capital"}
DESC = {"tr": "Castle: Borsa İstanbul'un bütün paylarını genç Buffett'ın yöntemiyle tarar: net-net, Graham ölçütleri, kâr verimi ve özel durumlar.",
        "en": "Castle screens every Borsa İstanbul share the way young Buffett did: net-nets, Graham's criteria, earnings yield and special situations."}
META_KEYS = ["cc", "name", "exchange", "cur", "asof", "data_notes", "en"]


def seo_head():
    e = lambda t: t.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
    canon = ('<script>(function(){var m=/[?&]lang=(tr|en)\\b/.exec(location.search),k=document.createElement("link");'
             'k.rel="canonical";k.href="%s"+(m?"?lang="+m[1]:"");document.head.appendChild(k);})();</script>' % SITE_URL)
    return ("<script>window.CASTLE_HEAD=" + json.dumps({"title": TITLE, "desc": DESC}, ensure_ascii=False).replace("<", "\\u003c") + ";</script>" + canon +
            '<link rel="alternate" hreflang="tr" href="%s?lang=tr"><link rel="alternate" hreflang="en" href="%s?lang=en">'
            '<link rel="alternate" hreflang="x-default" href="%s">' % (SITE_URL, SITE_URL, SITE_URL) +
            '<meta property="og:type" content="website"><meta property="og:site_name" content="Kose Capital">'
            '<meta property="og:title" content="%s"><meta property="og:description" content="%s">'
            '<meta property="og:url" content="%s"><meta property="og:image" content="https://www.kosecapital.com/og.png">'
            '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
            '<meta name="twitter:card" content="summary_large_image">'
            % (e("Castle · Borsa İstanbul değer taraması / value screen"), e(DESC["tr"] + " / " + DESC["en"]), SITE_URL))


def main():
    meta, core = load(J("data", CC, "meta.json")), load(J("data", CC, "core.json"))
    m = {k: meta[k] for k in META_KEYS if k in meta}
    doc = dict(v=3, cc=CC, built=datetime.date.today().isoformat(), meta=m, P=core["P"], rates=core["rates"], counts=core["counts"],
               U=core["U"], R=core["R"], counter=SITE.get("counter") or None)
    os.makedirs(J("docs", "data"), exist_ok=True)
    for f in os.listdir(J("docs", "data")):                # eski yöntemin dosyaları (öbür ülkeler, dünya haritası, arama dizini)
        if f not in ("TR.json", "summary.json"):
            os.remove(J("docs", "data", f))
    open(J("docs", "data", "TR.json"), "w", encoding="utf-8").write(dump(doc))
    k = core["counts"]
    # Kose Capital ana sayfasının okuduğu özet. `castles` eski adıyla durur: en az bir mercekten geçen şirket sayısı.
    summary = dict(built=doc["built"], asof=meta.get("asof"), countries=1, companies=k["n"], castles=k["any"], opportunities=k["any"],
                   lenses=dict(netnet=k["nn"], graham=k["gr"], earnings_yield=k["ey"], special=k["ws"]), queue=0)
    open(J("docs", "data", "summary.json"), "w", encoding="utf-8").write(dump(summary))
    open(J("docs", ".nojekyll"), "w").write("")
    tpl = open(J("pipeline", "template.html"), encoding="utf-8").read()
    assert tpl.count("/*__DATA__*/") == 1
    body = tpl.replace("/*__DATA__*/", dump(doc).replace("<", "\\u003c"))
    head = ('<!doctype html><html lang="tr"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="description" content="' + DESC["tr"] + ' / ' + DESC["en"] + '">' + seo_head() +
            '<style>:root{color-scheme:light;padding:env(safe-area-inset-top,0px) 0 env(safe-area-inset-bottom,0px)}'
            'body{margin:0;font:14px system-ui,sans-serif}[hidden]{display:none!important}</style></head><body>')
    site_body = body.replace("<title>Castle</title>", "<title>" + TITLE["tr"] + "</title>", 1)
    open(J("docs", "index.html"), "w", encoding="utf-8").write(head + site_body + "</body></html>")
    os.makedirs(J("dist"), exist_ok=True)
    open(J("dist", "castle.html"), "w", encoding="utf-8").write(body)
    os.makedirs(J(".preview"), exist_ok=True)
    open(J(".preview", "index.html"), "w", encoding="utf-8").write(head + site_body + "</body></html>")
    print(f'TR: {k["n"]} şirket | net-net {k["nn"]} | Graham {k["gr"]} | kâr verimi {k["ey"]} | özel durum {k["ws"]} | fırsat {k["any"]}')
    for f in ["docs/index.html", "dist/castle.html", "docs/data/TR.json", "docs/data/summary.json"]:
        print(f"  {f:24} {os.path.getsize(J(*f.split('/'))):>9,} bayt")


if __name__ == "__main__":
    main()
