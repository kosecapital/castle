// Kose Capital ziyaret sayacı: Cloudflare Worker + D1. Kurulum: counter/README.md
// Çerez kullanmaz; IP adresi ve tarayıcı bilgisi saklanmaz. Günlük tekil ziyaretçi, günlük değişen bir tuzla karıştırılmış
// özetten (hash) sayılır; özetler iki gün sonra silinir, bu yüzden bir ziyaretçi günler arasında izlenemez.
//
// Bağlantılar (Worker ayarlarında):
//   DB        : D1 veritabanı
//   STATS_KEY : istatistik sayfasının anahtarı (gizli metin)
//   SALT      : rastgele uzun bir metin (gizli)
//
//   GET|POST /hit?t=v|n&s=<site>&p=<sayfa>&r=<gelinen site>&l=<dil>   ziyaret (v) ya da sayfa içi gezinme (n) kaydı
//   GET      /?key=STATS_KEY[&days=30]                                 istatistik sayfası (HTML)
//   GET      /stats?key=STATS_KEY[&days=30]                            aynı veriler (JSON)

const ALLOWED = /^https:\/\/((www\.)?kosecapital\.com|kosecapital\.github\.io)$/;   // yalnız bu sitelerden gelen kayıt sayılır
const BOTS = /bot|crawl|spider|slurp|preview|monitor|headless|lighthouse|pingdom|curl|wget|python|scrapy|httpclient|facebookexternalhit|whatsapp|telegram/i;
const SCHEMA = [
  "CREATE TABLE IF NOT EXISTS daily (day TEXT PRIMARY KEY, views INTEGER NOT NULL DEFAULT 0, visitors INTEGER NOT NULL DEFAULT 0)",
  "CREATE TABLE IF NOT EXISTS dim (day TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL, n INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (day, kind, key))",
  "CREATE TABLE IF NOT EXISTS seen (day TEXT NOT NULL, h TEXT NOT NULL, PRIMARY KEY (day, h))",
];
let ready = false;

const dayOf = (ms) => new Date(ms + 3 * 3600 * 1000).toISOString().slice(0, 10);          // gün, İstanbul saatiyle
const clean = (s, n) => String(s || "").toLowerCase().replace(/[^a-z0-9._\-:/]/g, "").slice(0, n);

async function sha(text) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(b)].slice(0, 12).map((x) => x.toString(16).padStart(2, "0")).join("");
}
async function init(env) {
  if (ready) return;
  await env.DB.batch(SCHEMA.map((q) => env.DB.prepare(q)));
  ready = true;
}

async function hit(req, env, url) {
  const origin = req.headers.get("Origin") || "", ref = req.headers.get("Referer") || "", ua = req.headers.get("User-Agent") || "";
  let from = origin;
  if (!from && ref) { try { from = new URL(ref).origin; } catch (e) {} }
  if (!ALLOWED.test(from) || !ua || BOTS.test(ua)) return;                                // başka siteden ya da robottan gelen kayıt sayılmaz
  await init(env);
  const q = url.searchParams, day = dayOf(Date.now()), view = q.get("t") !== "n";
  const site = clean(q.get("s"), 20) || "site", page = clean(q.get("p"), 60), lang = clean(q.get("l"), 5);
  const refHost = clean(q.get("r"), 80), country = clean(req.cf && req.cf.country, 2).toUpperCase() || "??";
  const up = (kind, key) => env.DB.prepare("INSERT INTO dim (day, kind, key, n) VALUES (?1, ?2, ?3, 1) ON CONFLICT (day, kind, key) DO UPDATE SET n = n + 1").bind(day, kind, key);
  const st = [up("page", site + (page ? ":" + page : ""))];
  if (view) {
    const h = await sha(day + "|" + (env.SALT || "") + "|" + (req.headers.get("CF-Connecting-IP") || "") + "|" + ua);
    const r = await env.DB.prepare("INSERT OR IGNORE INTO seen (day, h) VALUES (?1, ?2)").bind(day, h).run();
    const fresh = r.meta && r.meta.changes ? 1 : 0;                                       // bugün ilk kez görülen ziyaretçi
    st.push(env.DB.prepare("INSERT INTO daily (day, views, visitors) VALUES (?1, 1, ?2) ON CONFLICT (day) DO UPDATE SET views = views + 1, visitors = visitors + ?2").bind(day, fresh));
    st.push(up("site", site));
    if (fresh) { st.push(up("country", country)); if (lang) st.push(up("lang", lang)); st.push(up("ref", refHost || "(doğrudan)")); }
    if (Math.random() < 0.02) st.push(env.DB.prepare("DELETE FROM seen WHERE day < ?1").bind(dayOf(Date.now() - 2 * 86400 * 1000)));
  }
  await env.DB.batch(st);
}

async function stats(env, days) {
  await init(env);
  const since = dayOf(Date.now() - (days - 1) * 86400 * 1000);
  const daily = (await env.DB.prepare("SELECT day, views, visitors FROM daily WHERE day >= ?1 ORDER BY day DESC").bind(since).all()).results;
  const dims = (await env.DB.prepare("SELECT kind, key, SUM(n) AS n FROM dim WHERE day >= ?1 GROUP BY kind, key ORDER BY n DESC").bind(since).all()).results;
  const all = await env.DB.prepare("SELECT COALESCE(SUM(views), 0) AS views, COALESCE(SUM(visitors), 0) AS visitors, MIN(day) AS first FROM daily").first();
  const by = {};
  for (const d of dims) (by[d.kind] = by[d.kind] || []).push([d.key, d.n]);
  return { days, since, today: dayOf(Date.now()), total: all, daily, by };
}

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
function page(s) {
  const n = (x) => Number(x || 0).toLocaleString("tr-TR");
  const sum = (k) => s.daily.reduce((a, d) => a + d[k], 0), today = s.daily.find((d) => d.day === s.today) || { views: 0, visitors: 0 };
  const mx = Math.max(1, ...s.daily.map((d) => d.views));
  const table = (title, rows, max) => "<section><h2>" + title + "</h2>" + (rows && rows.length ? "<table>" + rows.slice(0, max || 15).map((r) => "<tr><td>" + esc(r[0]) + "</td><td class=n>" + n(r[1]) + "</td></tr>").join("") + "</table>" : "<p class=m>Henüz kayıt yok.</p>") + "</section>";
  return `<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Kose Capital: ziyaretler</title>
<style>:root{color-scheme:light dark}body{font:15px/1.5 system-ui,sans-serif;max-width:920px;margin:0 auto;padding:20px 16px 48px}h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:22px 0 6px}.m{opacity:.65;font-size:13px}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}.k div{border:1px solid #8884;border-radius:10px;padding:10px 12px}.k b{display:block;font-size:24px}
table{border-collapse:collapse;width:100%}td{padding:4px 6px;border-bottom:1px solid #8883}.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:0 28px}.bar{display:inline-block;height:9px;border-radius:3px;background:#96690f;vertical-align:middle}</style>
<h1>Kose Capital: ziyaretler</h1><p class=m>Son ${s.days} gün (${esc(s.since)} sonrası), gün İstanbul saatiyle. Ziyaret = sayfanın bir kez açılması. Ziyaretçi = o gün ilk kez görülen tarayıcı. Çerez yok; kişisel veri saklanmıyor.</p>
<div class=k><div><span class=m>Bugün ziyaretçi</span><b>${n(today.visitors)}</b></div><div><span class=m>Bugün ziyaret</span><b>${n(today.views)}</b></div><div><span class=m>${s.days} günde ziyaretçi (günlüklerin toplamı)</span><b>${n(sum("visitors"))}</b></div><div><span class=m>${s.days} günde ziyaret</span><b>${n(sum("views"))}</b></div><div><span class=m>Baştan beri ziyaret${s.total.first ? " (" + esc(s.total.first) + "'den)" : ""}</span><b>${n(s.total.views)}</b></div></div>
<section><h2>Günler</h2>${s.daily.length ? "<table><tr><td class=m>Gün</td><td class='n m'>Ziyaretçi</td><td class='n m'>Ziyaret</td><td></td></tr>" + s.daily.map((d) => "<tr><td>" + d.day + "</td><td class=n>" + n(d.visitors) + "</td><td class=n>" + n(d.views) + "</td><td style='width:45%'><span class=bar style='width:" + Math.round((100 * d.views) / mx) + "%'></span></td></tr>").join("") + "</table>" : "<p class=m>Henüz kayıt yok.</p>"}</section>
<div class=g>${table("Site (ziyaret)", s.by.site)}${table("Ülke (ziyaretçi)", s.by.country)}${table("Nereden geldi (ziyaretçi)", s.by.ref)}${table("Dil (ziyaretçi)", s.by.lang)}</div>
${table("Sayfalar ve Castle'da açılan ülke ve şirketler (açılış sayısı)", s.by.page, 40)}
<p class=m>Başka aralık için adresin sonuna &amp;days=7 ya da &amp;days=90 ekle (en çok 365).</p></html>`;
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (url.pathname === "/hit") {
      ctx.waitUntil(hit(req, env, url).catch(() => {}));
      return new Response(null, { status: 204, headers: { "Access-Control-Allow-Origin": req.headers.get("Origin") || "*", "Cache-Control": "no-store" } });
    }
    if (url.pathname === "/" || url.pathname === "/stats") {
      if (!env.STATS_KEY || url.searchParams.get("key") !== env.STATS_KEY) return new Response("Anahtar gerekli.", { status: 401 });
      const s = await stats(env, Math.max(1, Math.min(365, parseInt(url.searchParams.get("days") || "30", 10) || 30)));
      if (url.pathname === "/stats") return Response.json(s, { headers: { "Cache-Control": "no-store" } });
      return new Response(page(s), { headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "Referrer-Policy": "no-referrer" } });
    }
    return new Response("Bulunamadı.", { status: 404 });
  },
};
