# Dinamik lig katalogu

V8.3, football-data.org tarafindan mevcut abonelige acik olarak listelenen
yarismalari otomatik gosterir. Katalogdaki bir ligin gorunmesi, o lig icin
tahmin modelinin dogrulandigi anlamina gelmez.

## Durumlar

- `VALIDATED`: Lig, V8.3 model kaydina ve dogrulanmis tahmin akişina sahiptir.
- `RESEARCH_REQUIRED`: Lig erisilebilir ancak tahmin uretilemez.
- `CATALOG_UNAVAILABLE`: Lig katalogu alinamadi; abonelik erisimi
  dogrulanamadigi icin tahmin devre disidir.
- `NOT_ACCESSIBLE`: Lig mevcut abonelik katalogunda yer almiyor.
- `SUFFICIENT_FOR_RESEARCH`: Mevcut sezon ham verisi arastirma icin yeterli
  gorunur; model dogrulamasi yerine gecmez.

Turkiye/Super Lig isaretli yarismalar katalogda once gosterilir. Kod veya
yarismaci kimligi sabitlenmez; API katalogu esas alinir.

## Yeni bir ligi tahmine acma

1. Kimlik dogrulamali `/competitions` yanitinda erisimi dogrula.
2. Yarismaya ait sezon ve tamamlanmis mac kapsamini incele.
3. Lig bazli model secimini sadece gecmis veriden yap.
4. Ayrilmis validation sezonunda market bazli performansi olc.
5. Canli motor/backtest paritesini calistir.
6. Ancak bunlardan sonra `MODEL_SELECTIONS` kaydi ekle.

Katalog veya veri hatalarinda tahmin uretilmez. API anahtari yalnizca ortam
degiskeninde tutulur; katalog yanitlari uzun TTL ile onbelleklenir.
