#!/usr/bin/env node
// Castle: bir ülke için sur geometrisi ve şirket noktalarının haritadaki yeri.
// Kullanım: node pipeline/geo.mjs TR      (girdi: data/TR/core.json + meta.json, çıktı: data/TR/geo.json)
//
// Noktaların yeri coğrafi değildir: bir şirket süzgeçte ne kadar ilerlediyse merkeze o kadar yakındır.
//   1. surda elenenler  -> ülkenin içinde, en dış surun dışında
//   2. surda elenenler  -> 1. ve 2. sur arasında (önce son 12 ay testinde kalanlar, içeride beş yıl testinde kalanlar)
//   3. sur (elenen ya da sırada bekleyen) -> 2. ve 3. sur arasında
//   fiyat aşamasına gelenler -> 3. ve 4. sur arasında bekler; kaleye girenlerin yerini sayfa hesaplar
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as topojson from "topojson-client";
import { geoArea } from "d3-geo";
import polylabel from "polylabel";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const cc = process.argv[2];
if (!cc) { console.error("kullanım: node pipeline/geo.mjs <ÜLKE KODU>"); process.exit(1); }
const dir = path.join(ROOT, "data", cc);
const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
const order = JSON.parse(fs.readFileSync(path.join(HERE, "countries.json"), "utf8")).countries.find((k) => k.cc === cc) || {};
const core = JSON.parse(fs.readFileSync(path.join(dir, "core.json"), "utf8"));
const w50 = JSON.parse(fs.readFileSync(path.join(HERE, "node_modules/world-atlas/countries-50m.json"), "utf8"));
const feat = topojson.feature(w50, w50.objects.countries).features.find((f) => String(f.id) === String(meta.iso));
if (!feat) throw new Error("ülke haritada yok: " + meta.iso);

const rad = Math.PI / 180;
const polys = feat.geometry.type === "Polygon" ? [feat.geometry.coordinates] : feat.geometry.coordinates;
const sized = polys.map((p) => ({ p, a: geoArea({ type: "Polygon", coordinates: p }) })).sort((a, b) => b.a - a.a);
// ana kara: en büyük parça ve onun en az dörtte biri büyüklüğündeki diğer parçalar (en çok beş)
const land = sized.filter((x, i) => i === 0 || (i < 5 && x.a >= 0.25 * sized[0].a)).map((x) => x.p);

function bbox(list) {
  let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
  for (const p of list) for (const q of p[0]) { if (q[0] < x0) x0 = q[0]; if (q[0] > x1) x1 = q[0]; if (q[1] < y0) y0 = q[1]; if (q[1] > y1) y1 = q[1]; }
  return [x0, y0, x1, y1];
}
const bb = bbox(land);
// düzlem yaklaşımı: boylamı merkez enlemin kosinüsüyle ölçekle
function planar(lon0, lat0) {
  const kx = Math.cos(lat0 * rad);
  return { to: ([lon, lat]) => [(lon - lon0) * kx, lat - lat0], from: ([x, y]) => [lon0 + x / kx, lat0 + y], kx };
}
function pole(poly, center) { // erişilmezlik kutbu: kıyıya en uzak iç nokta
  const pr = planar(center[0], center[1]);
  const pp = poly.map((ring) => ring.map(pr.to));
  const b = bbox([pp]);
  const size = Math.max(b[2] - b[0], b[3] - b[1]);
  const r = polylabel(pp, size * 0.002);
  return { c: pr.from([r[0], r[1]]), d: r.distance };
}
let pl = pole(sized[0].p, [(bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2]);
pl = pole(sized[0].p, pl.c); // bulunan noktanın enlemiyle bir kez daha: büyük ülkelerde bozulmayı azaltır
const G = Object.assign({}, order.geo || {}, meta.geo || {}); // ülkeye özel ayarlar: countries.json ya da meta.json içindeki "geo"
const C = G.c || pl.c.map((v) => Math.round(v * 1000) / 1000);
const PR = planar(C[0], C[1]);
const landP = land.map((p) => p.map((ring) => ring.map(PR.to)));
function ringArea(r) { let s = 0; for (let i = 0, j = r.length - 1; i < r.length; j = i++) s += (r[j][0] + r[i][0]) * (r[j][1] - r[i][1]); return Math.abs(s / 2); }
const landArea = landP.reduce((s, p) => s + ringArea(p[0]) - p.slice(1).reduce((t, h) => t + ringArea(h), 0), 0);
let R1 = G.R1 || 0.9 * pl.d;
if (!G.R1 && Math.PI * R1 * R1 > 0.42 * landArea) R1 = Math.sqrt((0.42 * landArea) / Math.PI); // sur, ülkenin yarısından azını kaplasın
const sig = (x) => Number(x.toPrecision(4));
const W = { c: C, R: [1, 1.45 / 2.4, 0.8 / 2.4, 0.4 / 2.4].map((f) => sig(R1 * f)), wait: sig((R1 * 0.62) / 2.4), keep: sig((R1 * 0.22) / 2.4) };

const U = core.U;
const by = (e, f) => U.filter((d) => d.e === e && (!f || f(d)));
const nA = by(2, (x) => x.w === "roe_ttm").length, nB = by(2, (x) => x.w !== "roe_ttm").length;
W.Rm = sig(Math.sqrt(W.R[1] ** 2 + (W.R[0] ** 2 - W.R[1] ** 2) * (nA + nB ? nB / (nA + nB) : 0.5)));
// görünüm: ana karaya yakın büyüklükteki parçalar da kadraja girer (Japonya'da Kyushu, İtalya'da Sicilya gibi)
const fitMin = G.fitMin == null ? 0.06 : G.fitMin;
const fb = bbox(sized.filter((x, i) => i === 0 || x.a >= fitMin * sized[0].a).map((x) => x.p));
bb[0] = Math.min(bb[0], fb[0]); bb[1] = Math.min(bb[1], fb[1]); bb[2] = Math.max(bb[2], fb[2]); bb[3] = Math.max(bb[3], fb[3]);
const latc = (bb[1] + bb[3]) / 2;
W.fit = G.fit || { c: [sig((bb[0] + bb[2]) / 2), sig(latc)], hw: sig(((bb[2] - bb[0]) / 2) * Math.cos(latc * rad) * 1.06), hh: sig(((bb[3] - bb[1]) / 2) * 1.06) };

// ---- yardımcılar ----
function dest([lon, lat], brg, dist) {
  const f1 = lat * rad, l1 = lon * rad, th = brg * rad, dl = dist * rad;
  const f2 = Math.asin(Math.sin(f1) * Math.cos(dl) + Math.cos(f1) * Math.sin(dl) * Math.cos(th));
  const l2 = l1 + Math.atan2(Math.sin(th) * Math.sin(dl) * Math.cos(f1), Math.cos(dl) - Math.sin(f1) * Math.sin(f2));
  return [l2 / rad, f2 / rad];
}
function gdist(a, b) {
  const f1 = a[1] * rad, f2 = b[1] * rad, dl = (b[0] - a[0]) * rad;
  const h = Math.sin((f2 - f1) / 2) ** 2 + Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) ** 2;
  return (2 * Math.asin(Math.sqrt(h))) / rad;
}
function inRing(pt, r) { let c = false; for (let i = 0, j = r.length - 1; i < r.length; j = i++) { if ((r[i][1] > pt[1]) !== (r[j][1] > pt[1]) && pt[0] < ((r[j][0] - r[i][0]) * (pt[1] - r[i][1])) / (r[j][1] - r[i][1]) + r[i][0]) c = !c; } return c; }
function inPoly(pt, p) { if (!inRing(pt, p[0])) return false; for (let i = 1; i < p.length; i++) if (inRing(pt, p[i])) return false; return true; }
function rng(seed) { return () => { let t = (seed += 0x6d2b79f5); t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
const rnd = rng(20261110);
const placed = []; // düzlem koordinatlarında, sıkışmayı önlemek için
function best(gen, k) {
  let bp = null, bd = -1;
  for (let i = 0; i < k; i++) {
    const p = gen(); if (!p) continue;
    const q = PR.to(p);
    let d = Infinity; for (const o of placed) { const x = Math.hypot(q[0] - o[0], q[1] - o[1]); if (x < d) d = x; }
    if (d > bd) { bd = d; bp = p; }
  }
  if (bp) placed.push(PR.to(bp));
  return bp;
}
const boxes = landP.map((p) => bbox([p]));
const areas = landP.map((p) => ringArea(p[0]));
const areaSum = areas.reduce((s, a) => s + a, 0);
function inLandOutside(rOut) {
  for (let i = 0; i < 600; i++) {
    let t = rnd() * areaSum, k = 0; while (k < areas.length - 1 && t > areas[k]) { t -= areas[k]; k++; }
    const b = boxes[k];
    const q = [b[0] + rnd() * (b[2] - b[0]), b[1] + rnd() * (b[3] - b[1])];
    if (!inPoly(q, landP[k])) continue;
    const p = PR.from(q);
    if (gdist(p, C) < rOut) continue;
    return p;
  }
  return null;
}
function inAnnulus(r0, r1) { return dest(C, rnd() * 360, Math.sqrt(r0 * r0 + rnd() * (r1 * r1 - r0 * r0))); }
function ringSlots(n, r, phase) { return Array.from({ length: n }, (_, i) => dest(C, phase + (360 * i) / n, r)); }
function bearing(a, b) { const y = Math.sin((b[0] - a[0]) * rad) * Math.cos(b[1] * rad), x = Math.cos(a[1] * rad) * Math.sin(b[1] * rad) - Math.sin(a[1] * rad) * Math.cos(b[1] * rad) * Math.cos((b[0] - a[0]) * rad); return ((Math.atan2(y, x) / rad) + 360) % 360; }

// ---- yerleşim: büyük şirketler önce yerleşir, böylece daha iyi yayılırlar ----
const pos = {}, ang = {};
const sortM = (a, b) => b.m - a.m;
let fellBack = 0;
for (const d of by(1).sort(sortM)) {
  let p = best(() => inLandOutside(W.R[0] * 1.07), 14);
  if (!p) { p = best(() => inAnnulus(W.R[0] * 1.08, W.R[0] * 1.9), 14); fellBack++; } // kara yetmezse surun çevresine
  pos[d.c] = p;
}
for (const d of by(2, (x) => x.w === "roe_ttm").sort(sortM)) pos[d.c] = best(() => inAnnulus(W.Rm * 1.03, W.R[0] * 0.95), 14);
for (const d of by(2, (x) => x.w !== "roe_ttm").sort(sortM)) pos[d.c] = best(() => inAnnulus(W.R[1] * 1.08, W.Rm * 0.97), 14);
const e3 = by(3).sort((a, b) => a.c.localeCompare(b.c));
if (e3.length <= 12) ringSlots(e3.length, (W.R[1] + W.R[2]) / 2, 12).forEach((p, i) => (pos[e3[i].c] = p));
else for (const d of e3.sort(sortM)) pos[d.c] = best(() => inAnnulus(W.R[2] * 1.12, W.R[1] * 0.93), 14);
const e4 = by(4).sort((a, b) => a.c.localeCompare(b.c));
if (e4.length <= 10) ringSlots(e4.length, W.wait, 40).forEach((p, i) => { pos[e4[i].c] = p; ang[e4[i].c] = Math.round((40 + (360 * i) / e4.length) * 10) / 10; });
else for (const d of e4.sort(sortM)) { const p = best(() => inAnnulus(W.R[3] * 1.3, W.R[2] * 0.9), 14); pos[d.c] = p; ang[d.c] = Math.round(bearing(C, p) * 10) / 10; }

const digits = Math.min(6, Math.max(3, Math.ceil(2 - Math.log10(R1)) + 1));
const f = 10 ** digits;
for (const d of U) { if (!pos[d.c]) throw new Error("konum yok: " + d.c); pos[d.c] = pos[d.c].map((v) => Math.round(v * f) / f); }
fs.writeFileSync(path.join(dir, "geo.json"), JSON.stringify({ W, pos, ang }));
console.log(cc, "kutup", pl.c.map((v) => v.toFixed(2)).join(","), "iç yarıçap", pl.d.toFixed(3), "| W", JSON.stringify(W), "| şirket", U.length, "| karaya sığmayan", fellBack, "| kara parçası", land.length);
