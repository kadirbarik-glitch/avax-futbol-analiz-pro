# Champions League veri araştırması

CL 2023, 2024 ve 2025 verileri sürümlenmiş test fixture'ı değildir. Ham
football-data.org yanıtları yerel `data_cache/` dizininde tutulur ve Git'e
eklenmez.

## Normal geliştirme ve CI

Normal CI gerçek API veya CL cache gerektirmez. `test_v82_cl_parity_fixture`
deterministik, sentetik bir veri setiyle canlı motor/backtest paritesini
denetler. Bu fixture gerçek Şampiyonlar Ligi performansı kanıtı değildir.

Gerçek-cache parite testleri cache yoksa `skipped` olarak raporlanır; bu
başarı değildir. Gerçek veri zorunlu olduğunda `REQUIRE_CL_CACHE=1` ayarı
cache eksikliğini hata yapar.

## Kontrollü gerçek veri araştırması

İlk olarak mevcut cache ile ağ erişimi olmadan doğrulama yapılır:

```powershell
.\.venv\Scripts\python.exe backtest_v82.py
.\.venv\Scripts\python.exe test_v82_real_data.py --require-manifest
.\.venv\Scripts\python.exe -m unittest -v test_v82_backtest_parity
```

Eksik veya geçersiz sezonlar yalnızca yetkili bir ortamda, anahtarı terminale
veya dosyaya yazmadan açıkça indirilebilir:

```powershell
.\.venv\Scripts\python.exe backtest_v82.py --download
```

Bu komut `FOOTBALL_DATA_API_KEY` ortam değişkenini kullanır. Anahtar kaynak
koda, loglara veya manifest'e yazılmaz.

Başarılı araştırma sonrasında `CL_manifest.json`, her sezon dosyasının
SHA-256 özeti ile ham/geçerli maç sayılarını kaydeder. Manifest, veri
bütünlüğünü doğrular; model isabeti veya sağlayıcı lisans izni anlamına
gelmez. Ham veriyi artifact olarak paylaşmadan önce veri sağlayıcının saklama
ve yeniden dağıtım koşulları ayrıca doğrulanmalıdır.
