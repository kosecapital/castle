# Avustralya: yayımlanmadı (16 Kasım 2026)

Veri 15 Kasım 2026'da geldi (1.563 şirket, 120 aday, oran sayfalarının hepsi tamam). İki denetim tutmadığı için ülke eklenmedi; `meta.json` yazılmadı, veri yerine alınmadı.

## Tutmayan denetimler

1. **`pb_fix`, yön ters.** Toplayıcının `cur` yoluyla tamamladığı PD/DD artı; şirketin son bilançosunda özsermaye eksi.
   - FDC (FDC Consolidated Holdings): toplayıcı 12,16 (özsermaye yaklaşık +98,5 milyon dolar). 30 Haziran 2026 bilançosu: net yükümlülük 94,241 milyon dolar. Halka arz 13 Temmuz 2026'da, bilanço tarihinden sonra tamamlandı (350 milyon dolar); artı rakamı yazan bir belge bulunamadı. https://bulletin.webull.com/qbd/announcement/20260827/499509578/0cc1c6594184cff5b84093927c0c0a05.pdf
   - ACS (Accent Resources): toplayıcı 22,21 (yaklaşık +4,5 milyon). 30 Haziran 2026 yıllık raporu: net yükümlülük 1,352 milyon dolar. https://announcements.asx.com.au/asxpdf/20260930/pdf/074rx94nrg3j14.pdf
   - CLAUDE.md: "Fark daha büyükse ya da yönü tersse yayımlama." `pbs` dolu 33 satırın hepsi zararda ya da kâr verisi yok; hiçbiri 1. suru geçmiyor. Yani sonuç değişmiyor, ama kural açık. NMR ve SCX denenmedi.
2. **`pe_fix`, %10 dışında.** Özsermaye kârlılığından hesaplanan iki F/K da tutmadı (ülkede bu yolla hesaplanan yalnız iki şirket var).
   - MGH (Maas Group): toplayıcı 18,64. 2026 mali yılı Appendix 4E: ana ortaklık kârı 136,112 milyon dolar, hisse başına 37,7 sent -> F/K yaklaşık 10,3. Kârın 61,231 milyonu durdurulan faaliyet (Heidelberg Materials'a satılan yapı malzemeleri işi); yalnız süren faaliyetle yaklaşık 16,9. https://announcements.asx.com.au/asxpdf/20260820/pdf/072ywf50h52qzc.pdf
   - P1E (Pure One): toplayıcı 1,62; ikinci kaynaklarla 1,9-2,2. Piyasa değeri 12,8 milyon; zaten `mcapMin` altında.

## Tutan denetimler

- `ok` doğru, `errors` boş; oran sayfası 120/120.
- Şirket sayısı: ASX, Ekim 2026 için 1.893 kote şirket yazıyor (borç ihraççıları dahil 2.053). Evren 1.563: %17,4 eksik; %15-25 bandında, notla yayımlanabilir. Evrende olmayanlar: Rio Tinto Ltd (RIO), büyük yatırım şirketleri (AFI, ARG, WAM, BKI), ana kotasyonu başka ülkede olanlar (RMD, NEM, JHX, FPH, AMC, NWS). https://www.asx.com.au/about/market-statistics/historical-market-statistics
- İlk beş: ANZ ikinci kaynakla birebir (13 Kasım); CBA, WBC, NAB, BHP eski sayfalar fiyata ölçeklenince %3 içinde. BHP piyasa değeri şirketin tamamı (5.084 milyon pay).
- Enflasyon (ABS, aralık çeyreği yıllık): 2021 %3,5; 2022 %7,8; 2023 %4,1; 2024 %2,4; 2025 %3,8 (toplayıcının 2,87'si yıllık ortalama, kullanılmayacak). Son oran: Eylül 2026, %4,3.
- `nodata_top` listelerinde bilinen büyük şirket yok.

## Alper'in kararı gereken

Bu iki denetim yalnız zarardaki ve çok küçük şirketleri etkiliyor. Seçenekler: (a) dört şirketi `fixes.json` ile belgeden düzeltip yayımlamak, (b) kuralı "yalnız 1. suru geçebilecek şirketlerde" diye daraltmak (kural 2: yalnız Alper), (c) toplayıcıdaki `cur` yolunu incelemek. Karar gelene kadar ülke bekler; sonraki çalıştırma aynı denetimi yeniden yapar.
