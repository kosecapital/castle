// Yayından önce sayfa denemesi. Kullanım: node pipeline/check_site.cjs TR US
// .preview klasörünü kendisi sunar (önce `python3 pipeline/build_site.py` çalışmış olmalı). Bir denetim tutmazsa 1 koduyla çıkar.
// Bakılanlar: ülke açılıyor mu, beş adım geziliyor mu, şirket sayfası ve yöntem açılıyor mu, iki dil de çalışıyor mu,
// sayfada "undefined" ya da "NaN" var mı, telefonda yatay taşma var mı, konsolda hata var mı.
// Arama: dünya görünümünde yazılan hisse kodu bulunuyor ve şirketin sayfasını açıyor mu.
// Finansman kolu: düzeltme uygulanan şirketin sayfasında açıklaması iki dilde görünüyor mu (ülkede varsa).
// Saklanan rapor: raporu yazılmış bir şirket elenmiş gibi gösterilir (deneme verisiyle); raporu uyarıyla görünüyor mu, 4. sur listesinde izi var mı.
// Sonda bir kez: sayfa başka bir sitenin çerçevesinde (Wix) düzgün çalışıyor mu.
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const ROOT = path.join(__dirname, '..', '.preview');
const TYPES = { '.html': 'text/html; charset=utf-8', '.json': 'application/json', '.js': 'text/javascript' };

(async () => {
  const ccs = process.argv.slice(2).map(s => s.toUpperCase());
  if (!ccs.length) { console.log('kullanım: node pipeline/check_site.cjs <ÜLKE> [<ÜLKE> ...]'); process.exit(2); }
  const server = http.createServer((req, res) => {
    const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0].split('#')[0]).replace(/^\/+/, '') || 'index.html');
    fs.readFile(p, (e, buf) => { if (e) { res.writeHead(404); res.end(); } else { res.writeHead(200, { 'content-type': TYPES[path.extname(p)] || 'application/octet-stream' }); res.end(buf); } });
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const base = 'http://127.0.0.1:' + server.address().port + '/index.html';
  const browser = await chromium.launch();
  const fails = [], errs = [];
  const ok = (c, m) => { if (!c) fails.push(m); };
  const open = async (w, h, url) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1, locale: 'tr-TR' });
    const page = await ctx.newPage();
    page.on('console', m => { if (m.type() === 'error' && !/fonts\.g|ERR_|Failed to load resource/.test(m.text())) errs.push(m.text()); });
    page.on('pageerror', e => errs.push('pageerror: ' + e.message));
    await page.goto(url); await page.waitForTimeout(3600);
    return page;
  };
  const text = (page, sel) => page.$eval(sel, e => e.innerText).catch(() => '');
  const slug = (c) => String(c).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  const data = (cc) => JSON.parse(fs.readFileSync(path.join(ROOT, 'data', cc + '.json'), 'utf8'));
  const clean = async (page, tag) => { const t = await text(page, '#app'); const m = t.match(/.{0,50}(undefined|NaN|\[object).{0,50}/); ok(!m, tag + ': sayfada bozuk metin: ' + (m ? m[0] : '')); };

  for (const cc of ccs) {
    const tag = cc + ': ';
    const page = await open(1280, 800, base + '?lang=tr#' + cc.toLowerCase());
    ok(/veri \d/.test(await text(page, '#sub')), tag + 'ülke açılmadı (üst şerit: ' + (await text(page, '#sub')) + ')');
    for (let i = 1; i <= 5; i++) {
      await page.click('#steps button[data-go="' + i + '"]'); await page.waitForTimeout(1700);
      ok((await page.getAttribute('#steps button[data-go="' + i + '"]', 'aria-current')) === 'step', tag + i + '. adıma geçilemedi');
      ok((await text(page, '#panel')).length > 80, tag + i + '. adımda panel boş');
      await clean(page, tag + 'adım ' + i);
      if (i === 4 || i === 5) {
        const b = await page.$('#panel .card[data-c], #panel .rows button[data-c]');
        if (b) {
          await b.click(); await page.waitForTimeout(700);
          const t = await text(page, '#panel');
          ok(/Süzgeçteki yolu/.test(t), tag + 'şirket sayfası açılmadı (adım ' + i + ')');
          await clean(page, tag + 'şirket sayfası');
          await page.evaluate(() => document.querySelector('#lang button[data-lang="en"]').click()); await page.waitForTimeout(500);
          const e = await text(page, '#panel');
          ok(/Path through the filter/.test(e), tag + 'şirket sayfası İngilizceye geçmedi');
          ok(!/Süzgeçteki yolu|Piyasa değeri|Son bilanço dönemi/.test(e), tag + 'İngilizce sayfada Türkçe başlık kaldı');
          await clean(page, tag + 'şirket sayfası (EN)');
          await page.evaluate(() => document.querySelector('#lang button[data-lang="tr"]').click()); await page.waitForTimeout(300);
          await page.click('#panel .back'); await page.waitForTimeout(300);
        }
      }
    }
    await page.click('#method'); await page.waitForTimeout(400);
    const m = await text(page, '#sheetin');
    ok(/İlkeler ve kaynakları/.test(m) && /Veri ve sınırlar/.test(m) && !/undefined|NaN/.test(m), tag + 'yöntem sayfası eksik ya da bozuk');
    await page.evaluate(() => document.querySelector('#lang button[data-lang="en"]').click()); await page.waitForTimeout(400);
    const me = await text(page, '#sheetin');
    ok(/Principles and their sources/.test(me) && !/undefined|NaN/.test(me), tag + 'yöntem sayfası İngilizcede bozuk');
    await page.context().close();
    const D = data(cc), ci = D.cols.indexOf('c'), mi = D.cols.indexOf('m'), ei = D.cols.indexOf('e');
    // arama: dünya görünümünde (ülkeye girmeden) en büyük şirketin kodu yazılır
    {
      const big = D.rows.slice().sort((a, b) => b[mi] - a[mi])[0][ci], sp = await open(1280, 800, base + '?lang=tr');
      await sp.click('#q'); await sp.keyboard.type(big, { delay: 30 }); await sp.waitForTimeout(1500);
      const hit = await sp.$('#ql button[data-enter="' + cc + '"][data-sel="' + big + '"]');
      ok(!!hit, tag + 'dünya görünümünde arama ' + big + ' kodunu bulamadı (liste: ' + (await text(sp, '#ql')).replace(/\n/g, ' ').slice(0, 80) + ')');
      if (hit) {
        await hit.click(); await sp.waitForTimeout(4200);
        ok(/Süzgeçteki yolu/.test(await text(sp, '#panel')) && sp.url().endsWith('#' + cc.toLowerCase() + '-' + slug(big)), tag + 'aramadan ' + big + ' sayfası açılmadı (' + sp.url().split('/').pop() + ')');
        await clean(sp, tag + 'aramadan açılan şirket sayfası');
      }
      await sp.context().close();
    }
    // finansman kolu düzeltmesi uygulanan şirket: açıklama iki dilde görünmeli
    const arm = Object.keys(D.F || {}).find(c => D.F[c].on);
    if (arm) {
      const ap = await open(1280, 800, base + '?lang=tr#' + cc.toLowerCase() + '-' + slug(arm));
      const t = await text(ap, '#panel');
      ok(/finansman kolu hariç/.test(t) && /Kol hariç net borç/.test(t) && /Kaynak:/.test(t), tag + arm + ': finansman kolu açıklaması görünmüyor');
      await clean(ap, tag + arm + ' (finansman kolu)');
      await ap.evaluate(() => document.querySelector('#lang button[data-lang="en"]').click()); await ap.waitForTimeout(500);
      const e = await text(ap, '#panel');
      ok(/excluding the finance arm/.test(e) && /Net debt without the arm/.test(e) && !/finansman kolu|Kol hariç/.test(e), tag + arm + ': finansman kolu açıklaması İngilizcede eksik ya da Türkçe kaldı');
      await clean(ap, tag + arm + ' (finansman kolu, EN)');
      await ap.context().close();
    }
    // saklanan rapor: raporu olan ilk şirket 2. surda elenmiş gibi gösterilir (yalnız bu denemede, veri dosyasına dokunmadan)
    const kept = D.rows.map(r => r[ci]).find(c => D.R[c] && D.rows.find(r => r[ci] === c)[ei] === 4);
    if (kept) {
      const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 1, locale: 'tr-TR' });
      const rp = await ctx.newPage(); rp.on('pageerror', e => errs.push('pageerror: ' + e.message));
      await rp.route('**/data/' + cc + '.json', async route => {
        const r = await route.fetch(), j = await r.json(), wi = j.cols.indexOf('w');
        if (!j.whys.includes('loss')) j.whys.push('loss');
        const row = j.rows.find(x => x[ci] === kept); row[ei] = 2; row[wi] = j.whys.indexOf('loss');
        j.L2[kept].fails = [{ k: 'loss', v: ['2025'] }]; j.L2[kept].ok = 0;
        j.RX = j.RX || {}; j.RX[kept] = j.R[kept]; delete j.R[kept];
        await route.fulfill({ response: r, json: j });
      });
      await rp.goto(base + '?lang=tr#' + cc.toLowerCase() + '-' + slug(kept)); await rp.waitForTimeout(4200);
      const t = await text(rp, '#panel');
      ok(/2\. surda elendi/.test(t) && /Saklanan rapor/.test(t) && /güncellenmiyor/.test(t) && /Kaynaklar/.test(t), tag + kept + ': elenen şirketin saklanan raporu görünmüyor');
      await clean(rp, tag + kept + ' (saklanan rapor)');
      await rp.click('#panel .back'); await rp.waitForTimeout(300);
      await rp.click('#steps button[data-go="5"]'); await rp.waitForTimeout(1900);
      const s5 = await text(rp, '#panel');
      ok(/Buraya gelmişti, şimdi elendi/.test(s5) && s5.includes(kept), tag + '4. sur görünümünde elenen ' + kept + ' için iz yok');
      await rp.evaluate(() => document.querySelector('#lang button[data-lang="en"]').click()); await rp.waitForTimeout(400);
      ok(/Reached this stage earlier, now eliminated/.test(await text(rp, '#panel')), tag + '4. sur görünümündeki iz İngilizcede yok');
      await clean(rp, tag + '4. sur (saklanan rapor, EN)');
      await ctx.close();
    }
    const ph = await open(390, 844, base + '?lang=en#' + cc.toLowerCase());
    ok((await ph.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)) <= 0, tag + 'telefonda yatay taşma');
    await clean(ph, tag + 'telefon (EN)');
    await ph.context().close();
  }
  // Gömülü kullanım (Wix'teki gibi başka bir sitenin çerçevesinde): üst sayfanın kaydırması engellenmemeli, düğmeler çerçevenin içinde olmalı ve çalışmalı
  {
    const port = server.address().port;
    const host = http.createServer((req, res) => { res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); res.end('<!doctype html><body style="margin:0"><div style="height:120px"></div><iframe id="f" src="http://127.0.0.1:' + port + '/index.html?lang=tr" style="display:block;border:0;width:980px;height:620px" sandbox="allow-same-origin allow-forms allow-popups allow-scripts allow-pointer-lock"></iframe><div style="height:1600px"></div></body>'); });
    await new Promise(r => host.listen(0, '127.0.0.1', r));
    const ctx = await browser.newContext({ viewport: { width: 1100, height: 800 }, deviceScaleFactor: 1, locale: 'tr-TR' });
    const page = await ctx.newPage(); page.on('pageerror', e => errs.push('pageerror: ' + e.message));
    await page.goto('http://localhost:' + host.address().port + '/'); await page.waitForTimeout(3400);
    const fr = page.frames().find(f => f.url().includes('index.html')), box = await (await page.$('#f')).boundingBox();
    const st = () => fr.evaluate(() => { const a = document.querySelector('#steps button[aria-current="step"]'); return a ? a.getAttribute('data-go') : null; });
    const mid = (sel) => fr.evaluate((q) => { const el = document.querySelector(q); if (!el) return { x: 0, y: 0, inside: false }; const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2, inside: r.width > 0 && r.top >= 0 && r.bottom <= innerHeight && r.right <= innerWidth }; }, sel);
    ok(await fr.evaluate(() => document.documentElement.classList.contains('embed')), 'gömme: sayfa çerçevede olduğunu anlamadı');
    ok((await mid('#full')).inside, 'gömme: "Tam ekran" bağlantısı görünmüyor');
    const map = await mid('#map'), s0 = await st();
    await page.mouse.move(box.x + map.x, box.y + map.y); await page.mouse.wheel(0, 300); await page.waitForTimeout(700);
    ok((await page.evaluate(() => window.scrollY)) > 100 && (await st()) === s0, 'gömme: tekerlek üst sayfayı kaydırmıyor ya da adımı değiştiriyor');
    await page.evaluate(() => window.scrollTo(0, 0)); await page.waitForTimeout(200);
    for (const want of ['1', '2']) {
      const next = await mid('#next'); ok(next.inside, 'gömme: "Yaklaş" düğmesi çerçevenin dışında');
      await page.mouse.click(box.x + next.x, box.y + next.y); await page.waitForTimeout(want === '1' ? 3200 : 1900);
      ok((await st()) === want, 'gömme: "Yaklaş" düğmesi ' + want + '. adıma geçirmedi (adım ' + (await st()) + ')');
    }
    await ctx.close(); host.close();
  }
  await browser.close(); server.close();
  ok(!errs.length, 'konsol hataları: ' + errs.slice(0, 5).join(' | '));
  console.log(fails.length ? 'TUTMAYANLAR:\n - ' + fails.join('\n - ') : 'sayfa denemesi tamam: ' + ccs.join(', ') + ' (iki dil, beş adım, şirket sayfası, yöntem, arama, finansman kolu, saklanan rapor, telefon, gömme)');
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error('deneme çalışmadı:', e.message); process.exit(1); });
