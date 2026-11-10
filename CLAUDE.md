# Castle: çalışma kılavuzu

Castle, bir ülkedeki bütün halka açık şirketleri Buffett ve Munger ilkeleriyle dört "sur"dan geçiren, haritalı bir değer yatırımı sayfasıdır.
Sahibi Alper Köse (Kose Capital). Site bu depodaki `docs/` klasöründen GitHub Pages ile yayımlanır ve Kose Capital'in Wix sitesine gömülüdür.
Bu dosya, bu depoda çalışan her Claude oturumunun (özellikle zamanlanmış görevlerin) uyacağı kılavuzdur.

## Değişmez kurallar

1. **Sayı uydurma.** Sitedeki her rakam bu çalıştırmada indirilen ya da okunan bir kaynaktan gelir. Kaynak yoksa alan boş kalır.
2. **Eşiklere dokunma.** `pipeline/params.json` ve surların kuralları yalnızca Alper açıkça isterse değişir. Sonuç beğenilmedi diye eşik oynatılmaz.
3. **Yatırım tavsiyesi yok.** Metinler "ölçütü geçti / geçemedi" der; "al", "sat", "tut" demez. Buffett ya da Munger'ın ağzından konuşulmaz, onlara söz atfedilmez.
4. **Sade Türkçe.** Kısa cümle, adım adım, önce sonuç sonra kanıt. Jargon ve çeviri kokan cümle yok. Sayılar Türkçe biçimde: `%12,5`, `1,2 milyar`, `10 Kasım 2026`.
5. **Kaynak göster.** Her şirket raporunun `sources` listesi dolu olur; haber ve bilanço cümlelerinin kaynağı orada bulunur.
6. **Emin değilsen yayımlama.** Aşağıdaki doğrulamalardan biri tutmazsa o ülkeyi yayımlama; neyin tutmadığını çalıştırma özetine yaz ve dur.
7. **Geçmişi silme.** `data/<ÜLKE>/reports.json` içindeki eski raporları silme; şirket elense bile rapor durur. Zorla gönderme (force push) yapma. Doğrudan `main` dalına gönder.
8. **Bekletilen ülkeler.** `pipeline/countries.json` içinde `hold` alanı olan ülke otomatik eklenmez.

## Depo düzeni

```
docs/                    yayımlanan site (GitHub Pages kökü). Elle düzenleme; build_site.py üretir.
  index.html, data/<ÜLKE>.json, data/world50.json
pipeline/
  countries.json         ülke sırası (borsa büyüklüğüne göre) ve ülkeye özel harita ayarları
  params.json            surların eşikleri
  charter.json           12 ilke ve dayandıkları Berkshire mektupları
  site.json              site ayarları (açılışta odaklanılan ülke, "sırada" metni)
  collect.py             TradingView tarayıcısından ülke verisi
  funnel.py              dört surun hesabı (internet kullanmaz)
  geo.mjs                harita üzerindeki sur ve nokta yerleri
  build_site.py          docs/ ve dist/castle.html üretir
  template.html          sayfanın kendisi (tek dosya; veri sonradan gömülür)
data/<ÜLKE>/
  meta.json              ülke ayarları: para birimi, enflasyon, yıllar, notlar
  universe.json          bütün şirketler (normalleştirilmiş)
  history.json           2. sur adayları için beş yıllık oranlar
  reports.json           3. sur puanları ve rapor metinleri (Claude yazar)
  core.json, geo.json    funnel.py ve geo.mjs çıktıları
  raw/                   indirilen ham veri (kanıt olarak saklanır)
```

## Komutlar

```bash
cd pipeline && npm install && cd ..        # bir kez (harita kitaplıkları)
pip install requests                        # bir kez (toplayıcı için)
python3 pipeline/collect.py probe <market>  # hangi alan dolu geliyor
python3 pipeline/collect.py universe <CC>   # data/<CC>/universe.json
python3 pipeline/funnel.py <CC>             # data/<CC>/core.json + ekrana özet
node pipeline/geo.mjs <CC>                  # data/<CC>/geo.json
python3 pipeline/build_site.py              # docs/ ve dist/castle.html
python3 -m http.server 8765 --directory .preview   # yerel deneme: http://127.0.0.1:8765
```

## Dört sur (özet; ayrıntı funnel.py içinde)

| Sur | Kural | Kaynak alan |
|---|---|---|
| 1. Kırmızı çizgiler | GYO ve yatırım ortaklığı değil; son 12 ayda net kâr var (F/K > 0); özsermaye pozitif; piyasa değeri ≥ `meta.mcapMin` | universe.json |
| 2. Kalite | Son 12 ay reel özsermaye kârlılığı ≥ %12. Beş yıllık geçmiş var, zarar yılı yok. Reel özsermaye kârlılığı ortalaması ≥ %15, hiçbir okuma < %10 değil. Net borç/FAVÖK ≤ 3. Serbest nakit akışı son beş dönemin en az ikisinde pozitif (finans şirketlerinde borç ve nakit testi yok) | universe.json + history.json |
| 3. Hendek ve yönetim | Claude'un yazdığı puanlar: B ≥ 2 ve A, C, D, E ≥ 1 | reports.json |
| 4. Fiyat | Temkinli F/K = PD/DD ÷ (son üç reel özsermaye kârlılığı okumasının en düşüğü). Adil çarpan = 100 ÷ (reel getiri eşiği − büyüme payı). Güvenlik marjı ≥ %25 ise "kale", değilse "kapıda bekliyor" | hesap |

"Reel": enflasyon muhasebesi (TMS/IAS 29) uygulayan şirketin rakamı zaten reeldir. Diğerlerinde nominal özsermaye kârlılığı o yılın tüketici enflasyonuyla düzeltilir: `(1+ROE)/(1+enflasyon) − 1`. `meta.deflate` değeri `all` ise bütün şirketler, `nominal_only` ise yalnız `nom=1` olanlar düzeltilir.

## İş A: yeni ülke ekle (her gün)

1. `pipeline/countries.json` sırasında, `data/<CC>/core.json` dosyası olmayan ve `hold` içermeyen **ilk** ülkeyi seç. Bir çalıştırmada en çok iki ülke.
2. **meta.json yaz.** Türkiye örneğini (`data/TR/meta.json`) şablon al. Doldurulacaklar:
   - `cc`, `iso`, `name`, `market` (countries.json'dan), `exchange` (borsanın Türkçe okunur adı), `cur` (para birimi kodu), `asof` (verinin kapanış tarihi), `fx` (1 ABD doları kaç yerel para).
   - `mcapMin`: yaklaşık 60 milyon ABD doları karşılığı, milyon yerel para biriminde, yuvarlak sayı. `small_text` ve `small_rule` cümlelerini buna göre yaz.
   - `years`: son beş mali yıl (eskiden yeniye). `era`: kalite ortalamasına giren okumalar; normal ülkede `years + ["cur"]`.
   - `cpi`: her yıl için yıl sonu yıllık tüketici enflasyonu (%), `cur` için en son yıllık oran. Kaynak: ülkenin istatistik kurumu ya da Dünya Bankası (`api.worldbank.org`, gösterge `FP.CPI.TOTL.ZG`). Kaynağı `data_notes` içine yaz.
   - `deflate`: çoğu ülkede `all`. Enflasyon muhasebesi uygulanan ülkelerde (countries.json'da `ias29` notu var: Türkiye, Arjantin) hangi şirketlerin uyguladığını doğrula; uygulamayan sektörleri `nominal_industries` listesine yaz ve `deflate: "nominal_only"` kullan.
   - `era_label`, `inflation_note`, `data_notes`, `chart_note`, `chart_note_nominal`: sayfada görünen Türkçe açıklamalar.
3. **Evreni indir:** `python3 pipeline/collect.py universe <CC>`.
4. **Toplayıcıyı doğrula** (her yeni ülkede; biri tutmazsa dur):
   - Şirket sayısı, borsanın kendi açıkladığı şirket sayısına yakın mı (±%15)?
   - En büyük beş şirketin fiyatı, piyasa değeri, F/K ve PD/DD değerleri ikinci bir kaynakla (örneğin stockanalysis.com) %5 içinde tutuyor mu? Piyasa değerinin para birimi doğru mu?
   - F/K dolu olan şirketlerin oranı makul mü (genelde %45-80)?
5. **Beş yıllık geçmiş** (`history.json`): yalnızca 1. suru ve son 12 ay kârlılık testini geçen adaylar için gerekir. `python3 pipeline/funnel.py <CC>` çıktısındaki `data` nedeniyle elenenler, geçmişi eksik adaylardır.
   - Önce toplayıcının geçmiş dizilerini (`*_fy_h`) kullan. Diziler boş geliyorsa aday başına `https://stockanalysis.com/quote/<borsa>/<KOD>/financials/ratios/` sayfasından ROE, ROIC, serbest nakit akışı verimi ve net borç/FAVÖK değerlerini al.
   - Biçim: `{"KOD": {"asof": "...", "stale": 0, "roe": [5 yıl + son 12 ay], "roic": [...], "fcf": [...], "nd": ..., "pe": ..., "pb": ..., "dy": ..., "po": ...}}`. Yüzdeler yüzde olarak (`17.0`), eksikler `null`.
6. **Süzgeci çalıştır:** `python3 pipeline/funnel.py <CC>`. 2. suru geçenler `pending` (sırada) görünür.
7. **3. sur: oku ve yaz** (aşağıdaki "Rapor yazımı"). Bir çalıştırmada en çok **25 şirket**. Sıra: önce fiyatı kale olmaya yetenler (dar hendek varsayımıyla güvenlik marjı ≥ %25, ardından geniş hendekle ≥ %25), sonra en büyük piyasa değerliler. Kalanlar "sırada" kalır; sonraki yenilemelerde okunur.
8. `python3 pipeline/funnel.py <CC> && node pipeline/geo.mjs <CC> && python3 pipeline/build_site.py`.
9. **Sayfayı dene:** `.preview` klasörünü sun, ülkeyi aç (`#cc`), beş adımı gez, konsolda hata olmadığını gör.
10. **Yayımla:** `git add -A && git commit -m "<Ülke> eklendi: N şirket, K kale" && git push origin main`.
11. **Özet yaz** (çalıştırmanın son mesajı): ülke, şirket sayıları (evren → 1 → 2 → 3 → kale), kaleler, sırada kalan sayısı, doğrulamada görülen sorunlar.

## İş B: yenileme (her ülke haftada bir)

1. `data/*/meta.json` içinde `asof` tarihi 7 günden eski olan ülkeleri bul; en eskiden başla. Bir çalıştırmada en çok **6 ülke**.
2. Her ülke için: evreni yeniden indir, gerekiyorsa `cpi.cur` ve `fx` değerlerini güncelle, adayların beş yıllık verisini yenile, `funnel.py` çalıştır.
3. **Öncekiyle karşılaştır** (`git diff` ya da eski `core.json`): 2. suru geçenlerin en az %70'i aynı kalmalı. Daha büyük bir değişim veri hatasına işarettir: yayımlama, özetle bildir.
4. **Raporlar:**
   - Yeni `pending` şirketleri oku (çalıştırma başına toplam 25 sınırı içinde).
   - Kale ve kapıda bekleyen şirketlerde yeni bilanço açıklandıysa (`per` değişti) ya da durum değiştiyse `latest`, gerekiyorsa `risks` ve puanları güncelle. Değişmeyenlere dokunma.
5. `asof` tarihini güncelle, derle, dene, gönder. Özet: hangi ülkeler yenilendi, kimin durumu değişti (kaleye giren, kaleden çıkan).

## Rapor yazımı (3. sur)

Her şirket için önce oku: şirketin ne yaptığı, sahiplik yapısı, son bilanço haberi, son bir yılın önemli olayları. En az iki bağımsız kaynak. Sonra `data/<CC>/reports.json` içine yaz:

```json
"KOD": {
  "scores": {"A": 2, "B": 2, "C": 1, "D": 2, "E": 1},
  "moat": "dar",
  "one": "Tek cümle: iş ve vardığımız sonuç (en çok 25 kelime).",
  "business": "2-4 cümle. Ne satar, parayı nasıl kazanır; bir iki somut rakam.",
  "moat_text": "Hendek neden bu sınıfta? Kanıt rakamla; zayıf yanı da yaz.",
  "mgmt": "Sahiplik, halka açıklık, kâr nereye gidiyor (temettü, borç, yatırım, geri alım).",
  "latest": "Tarihli son gelişme: 5 Kasım 2026: ... (rakamlarla).",
  "risks": ["Bu tezi ne bozar: 3-5 madde, her biri tam cümle"],
  "watch": ["İzlenecek 3-4 gösterge"],
  "sources": [{"t": "Kaynak adı: başlık (tarih)", "u": "https://..."}]
}
```

Puanlar:

- **A Anlaşılırlık (0-2):** 2 = ne sattığı ve parayı nasıl kazandığı iki cümleyle anlatılır. 1 = anlaşılır ama çok kollu ya da muhasebesi karmaşık. 0 = anlatılamıyor.
- **B Hendek (0-3):** 0 yok (emtia, ihale ya da teklifle alınan iş). 1 zayıf (üstünlük var ama kolay aşılır). 2 dar (gerçek ve rakamla kanıtlı: ölçek, lisans, marka; ama tek kaynağa bağlı ya da kalıcılığı belirsiz). 3 geniş (marka ve dağıtım ya da maliyet liderliği; rakibin yetişmesi yıllar ve büyük sermaye ister; fiyatlama gücü marjlarda görünür). `moat` alanı: 0 "yok", 1 "zayıf", 2 "dar", 3 "geniş".
- **C Kazancın öngörülebilirliği (0-2):** 2 = talep döngüden az etkilenir. 1 = döngüsel ama uzun vadede istikrarlı. 0 = kârın kaynağı belirsiz, tek seferlik ya da faaliyet dışı.
- **D Yönetim ve sermaye tahsisi (0-2):** 2 = kâr ana işe, borç ödemeye, temettü ya da geri alıma gidiyor. 1 = nötr ya da küçük kusur. 0 = ana iş dışı büyük finansal yatırım, değer yok eden satın alma ya da küçük ortağın aleyhine işlem.
- **E Dayanıklılık (0-2):** 2 = net nakit ya da düşük borç, çeşitlenmiş müşteri. 1 = makul borç, bir iki yoğunlaşma. 0 = tek müşteriye, tek sözleşmeye ya da tek bir kamu kararına bağlı.

Geçme koşulu: B ≥ 2 ve diğerleri ≥ 1. Elenen şirkette `risks` ve `watch` boş kalabilir; elenme nedeni `moat_text` ya da `mgmt` içinde açıkça yazılır.
İlkelerin kaynağı `pipeline/charter.json` içindedir; puan verirken oradaki ilkeleri uygula.

## Sayfa ve yayın

- Sayfa tek dosyadır (`pipeline/template.html`); veriyi `data/<CC>.json` dosyalarından yükler. Tasarımı, renkleri ve metinleri görev gerektirmedikçe değiştirme.
- Site: `git push origin main` sonrası GitHub Pages `docs/` klasörünü birkaç dakikada yayımlar.
- Claude'daki sayfa (isteğe bağlı): `dist/castle.html` dosyasını, `docs/data/` altındaki dosyalarla birlikte, `pipeline/site.json` içindeki `artifact` adresine yeniden yayımla. Yayın sorulursa ya da engellenirse atla; site asıl hedeftir.

## Çalıştırma özeti

Her çalıştırmanın son mesajı kısa bir Türkçe özet olur: ne yapıldı, hangi ülkeler, hangi sayılar, neyin tutmadığı. Bir şey yayımlanmadıysa nedenini ilk cümlede söyle.
