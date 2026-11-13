# Ziyaret sayacı

Site GitHub Pages'te durduğu için kendi başına sayamaz. Bu klasördeki küçük sunucu parçası (Cloudflare Worker) ziyaretleri kaydeder ve bir istatistik sayfası sunar. Kod bizim, veri Alper'in Cloudflare hesabındaki veritabanında durur.

## Ne sayar

- **Ziyaret:** sayfanın bir kez açılması.
- **Ziyaretçi:** o gün ilk kez görülen tarayıcı. Çerez yoktur. IP adresi ve tarayıcı bilgisi saklanmaz: ikisi günlük değişen bir tuzla karıştırılıp kısa bir özete çevrilir, özet iki gün sonra silinir. Bu yüzden aynı kişi ertesi gün yeni ziyaretçi sayılır ve günler arasında izlenemez.
- Ülke (Cloudflare'in verdiği ülke kodu), gelinen site, dil, ve Castle'da açılan ülke ve şirket sayfaları.
- Robotlar ve başka sitelerden gelen istekler sayılmaz.

## Kurulum (bir kez, yaklaşık 10 dakika)

1. https://dash.cloudflare.com adresinde ücretsiz hesap aç.
2. **Storage & Databases → D1 SQL Database → Create**: ad `kose_sayac`. Tabloları Worker ilk istekte kendisi kurar.
3. **Workers & Pages → Create → Worker ("Hello World")**: ad `kose-sayac`, **Deploy**.
4. **Edit code**: içindekileri sil, `counter/worker.js` dosyasının tamamını yapıştır, **Deploy**.
5. Worker'ın **Settings → Bindings → Add → D1 database**: değişken adı `DB`, veritabanı `kose_sayac`.
6. **Settings → Variables and Secrets → Add** (ikisi de "Secret"):
   - `STATS_KEY`: istatistik sayfasının anahtarı; kendin seç, uzun olsun.
   - `SALT`: rastgele uzun bir metin (klavyeye rastgele bas); bir daha gerekmez.
7. Worker'ın adresini kopyala (`https://kose-sayac.<hesap>.workers.dev`) ve Claude'a ver: `pipeline/site.json` içindeki `counter` alanına yazılır, site yeniden yayımlanır.
8. Ana sayfa (`kosecapital.github.io` deposu) için `counter/snippet.html` içindeki kodu, `SAYAC_ADRESI` yerine aynı adresi yazarak `</body>` etiketinden önce yapıştır.

## İstatistiklere bakmak

`https://kose-sayac.<hesap>.workers.dev/?key=<STATS_KEY>` (son 30 gün; `&days=7` ya da `&days=90` eklenebilir). Aynı veriler JSON olarak: `/stats?key=...`. Adresi yer imlerine ekle; anahtarı kimseyle paylaşma.

## Kodu değiştirmek

`counter/worker.js` değişirse yeni hâli Cloudflare'de 4. adımdaki gibi yeniden yapıştırılır. Depoya gönderilen kod Cloudflare'e kendiliğinden gitmez.
