# Castle

Bir ülkedeki bütün halka açık şirketleri Buffett ve Munger ilkeleriyle dört "sur"dan geçiren, haritalı değer yatırımı atlası. Türkçe ve İngilizce.
A value investing atlas that runs every listed company in a country through four "walls" built on the principles of Buffett and Munger. In Turkish and English.

- **Site:** <https://www.kosecapital.com/castle/> (İngilizce açılış için sonuna `?lang=en` ekle). `docs/` klasörü GitHub Pages ile yayımlanır. Ana sayfa: <https://www.kosecapital.com/> (ayrı depo: `kosecapital/kosecapital.github.io`).
- **Yöntem:** eşikler `pipeline/params.json`, ilkeler ve dayandıkları Berkshire Hathaway mektupları `pipeline/charter.json` içinde. Sayfadaki "Yöntem" düğmesi aynı bilgiyi gösterir.
- **Veri:** `.github/workflows/collect.yml` her gece sıradaki ülkelerin, cumartesi günü taranmış bütün ülkelerin verisini toplar ve `data/<ÜLKE>/in/` altına bırakır. Kaynaklar: TradingView tarayıcısı (Türkiye için İş Yatırım), stockanalysis.com oran sayfaları, IMF WEO ve Dünya Bankası enflasyon verisi.
- **Analiz ve yayın:** veriyi denetleyip siteye alan, şirket raporlarını yazan Claude oturumlarıdır. Kılavuz: `CLAUDE.md`.

Castle bir analiz aracıdır; yatırım tavsiyesi vermez. Castle is an analysis tool; it does not give investment advice.

## Derleme

```bash
cd pipeline && npm install && cd ..
python3 pipeline/accept.py --list            # gelen veri
python3 pipeline/funnel.py TR && node pipeline/geo.mjs TR && python3 pipeline/build_site.py
python3 -m http.server 8765 --directory .preview
```

Harita verisi: Natural Earth (world-atlas paketi).
