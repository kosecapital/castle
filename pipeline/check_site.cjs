// Yayından önce sayfa denemesi (genç Buffett yöntemi). Kullanım: node pipeline/check_site.cjs   (önce python3 pipeline/build_site.py)
// Bakılanlar: sayfa açılıyor mu, her sekme geziliyor mu, şirket defteri iki dilde açılıyor mu, yöntem açılıyor mu,
// sayfada "undefined" ya da "NaN" var mı, telefonda yatay taşma var mı, konsolda hata var mı. Bir denetim tutmazsa 1 koduyla çıkar.
const { chromium } = require('playwright');
const path = require('path');
const URL0 = 'file://' + path.join(__dirname, '..', '.preview', 'index.html');

(async () => {
  const browser = await chromium.launch();
  const fails = [], errs = [];
  const ok = (c, m) => { if (!c) fails.push(m); };
  const open = async (w, h, q) => {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    page.on('console', m => { if (m.type() === 'error' && !/fonts\.g|ERR_|Failed to load resource/.test(m.text())) errs.push(m.text()); });
    page.on('pageerror', e => errs.push('pageerror: ' + e.message));
    await page.goto(URL0 + q); await page.waitForTimeout(700);
    return page;
  };
  const text = (page, sel) => page.$eval(sel, e => e.innerText).catch(() => '');
  const clean = async (page, tag) => { const t = await text(page, '#app'); const m = t.match(/.{0,50}(undefined|NaN|\[object).{0,50}/); ok(!m, tag + ': sayfada bozuk metin: ' + (m ? m[0] : '')); };

  const page = await open(1280, 800, '?lang=tr');
  ok(/genç Buffett/.test(await text(page, '#sub')), 'üst şerit yüklenmedi');
  for (const t of ['any', 'nn', 'gr', 'ey', 'ws', 'near', 'all']) {
    await page.click('#tabs button[data-tab="' + t + '"]'); await page.waitForTimeout(150);
    ok((await page.getAttribute('#tabs button[data-tab="' + t + '"]', 'aria-pressed')) === 'true', t + ' sekmesine geçilemedi');
    await clean(page, 'sekme ' + t);
    const row = await page.$('tbody tr');
    if (row) {
      await row.click(); await page.waitForTimeout(200);
      ok(/Listeye dön/.test(await text(page, '#panel')), t + ': şirket defteri açılmadı');
      await clean(page, t + ' şirket defteri');
    }
  }
  await page.click('#lang button[data-lang="en"]'); await page.waitForTimeout(200);
  const e = await text(page, '#panel');
  ok(/Back to the list/.test(e) && !/Listeye dön|Piyasa değeri|Kâr verimi/.test(e), 'şirket defteri İngilizceye geçmedi');
  await clean(page, 'EN');
  await page.click('#method'); await page.waitForTimeout(200);
  ok(/Why young Buffett/.test(await text(page, '#sheetin')), 'yöntem açılmadı (EN)');
  await page.click('#shut');
  await page.click('#lang button[data-lang="tr"]'); await page.waitForTimeout(200);
  await page.click('#method'); ok(/Neden genç Buffett/.test(await text(page, '#sheetin')), 'yöntem açılmadı (TR)');

  const ph = await open(390, 844, '?lang=tr');
  ok(!(await ph.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), 'telefonda yatay taşma (liste)');
  const r = await ph.$('tbody tr');
  if (r) { await r.click(); await ph.waitForTimeout(200); ok(!(await ph.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), 'telefonda yatay taşma (defter)'); await clean(ph, 'telefon'); }
  await browser.close();
  errs.forEach(x => fails.push('konsol: ' + x));
  if (fails.length) { console.log('SAYFA DENEMESİ TUTMADI:\n  ' + fails.join('\n  ')); process.exit(1); }
  console.log('sayfa denemesi tamam');
})();
