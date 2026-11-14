# Fransa: taslak (14 Kasım 2026, yayımlanmadı)

Fransa bu çalıştırmada eklenmedi: şirket sayısı denetimi tutmadı (CLAUDE.md, İş A adım 2 ve kural 6).

## Tutmayan ve açık kalan denetimler
- **Şirket sayısı:** evren 573 pay (284 ana pazar, 241 Euronext Growth "AL", 48 Euronext Access "ML"). Bulunan tek resmî sayı: Euronext Investor Toolbox (18 Şubat 2026), Aralık 2025'te Euronext Paris'te 722 şirket (pazarlara bölünmemiş): https://www.euronext.com/en/media/15109/download . Fark %21; ±%15'in dışında. Farkın Euronext Access ve yabancı kotasyonlardan gelip gelmediği kaynakla gösterilemedi (AMF'nin Temmuz 2026 çalışması ve live.euronext.com listeleri açılamadı).
- **Piyasa değeri, özel oy payları:** Stellantis (STLAP) 13.386 milyon avro görünüyor; adi paylarla 10.208 milyon (2.906.201.733 pay × 3,5125; şirketin 1 Ekim 2026 sermaye bildirimi). Kaynak 866,5 milyon özel oy payını da sayıyor. Pluxee'de (PLX) aynı durum: evrende 2.490 milyon, adi paylarla yaklaşık 1.740 milyon.
- **PD/DD tutarsızlıkları:** Dekuple (DKUPL) evrende 2,735; oran sayfasında 1,49; özsermayeyle hesap 1,44. Viel (VIL) evrende 2,039; oran sayfasında 1,59 (azınlık dahil özsermaye); ana ortaklık özsermayesiyle 1,95. SEMCO (ALSEM) yaklaşık %6 yüksek.

## Tutan denetimler
- İlk beş şirket (L'Oréal, LVMH, TotalEnergies, Airbus, Schneider): fiyat 13 Kasım kapanışıyla aynı, piyasa değeri %4 içinde, PD/DD %1 içinde (abcbourse, rendementbourse). stockanalysis sayfası açılamadı.
- Toplayıcının F/K'sı: SCOR 7,88 (belgeyle 7,86), GEA 24,64 (belgeyle 24,7). PD/DD: Bouygues 1,354 (30 Haziran 2026 özsermayesiyle 1,354), LNA Santé 0,817 (0,822).
- Enflasyon (INSEE, aralık yıllık): 2021 %2,8; 2022 %5,9; 2023 %3,7; 2024 %1,3; 2025 %0,8. Ekim 2026: %3,4. `meta.json` taslağında yazılı.

## Bu klasörde
- `meta.json`: taslak (enflasyon oranları doğru; sayfa metinleri henüz yazılmadı).
- `reports.json`, `growth_facts.json`, `earn_facts.json`: 2. suru geçen 16 şirketin taslak raporları ve gerçek kayıtları. 3. suru geçenler: VIL, GTT, PLX, OR, AIR, RMS, BVI, PLNW, EQS, ALSEM. Elenenler: ALSTI, ALWEC, ALLEX, KOF, DKUPL, SWP.
- `verify.json`: yardımcı oturumların her şirket için doğrulama notları ve şüpheleri. **Ana oturum kale adaylarını (VIL, GTT) henüz kendi doğrulamadı.** PLX'te `permanent` kaydı (Brezilya PAT kararnamesi) ve GTT'de FAVÖK beklentisinin `guidance` olarak kullanılması ana oturumun kararını bekliyor.

Ülke eklenirken bu dosyalar `data/FR/` altına taşınır; raporların `per` alanı o günkü evrenle karşılaştırılır.
