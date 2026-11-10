# Castle

Bir ülkedeki bütün halka açık şirketleri Buffett ve Munger ilkeleriyle dört "sur"dan geçiren, haritalı değer yatırımı atlası.

- **Site:** `docs/` klasörü GitHub Pages ile yayımlanır.
- **Yöntem:** eşikler `pipeline/params.json`, ilkeler ve dayandıkları Berkshire Hathaway mektupları `pipeline/charter.json` içinde. Sayfadaki "Yöntem" düğmesi aynı bilgiyi gösterir.
- **Veri:** her ülkenin verisi `data/<ÜLKE>/` altında; ham indirmeler `raw/` klasöründe saklanır.
- **Çalışma kılavuzu:** `CLAUDE.md`.

Castle bir analiz aracıdır; yatırım tavsiyesi vermez.

## Derleme

```bash
cd pipeline && npm install && cd ..
python3 pipeline/funnel.py TR && node pipeline/geo.mjs TR && python3 pipeline/build_site.py
python3 -m http.server 8765 --directory .preview
```

Harita verisi: Natural Earth (world-atlas paketi).
