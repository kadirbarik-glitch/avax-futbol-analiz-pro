# AVAX V8.4 Beta · ayrı Render servisi

Bu beta, mevcut V8.3 Render servisine bağlı değildir. Yeni bir **Web Service**
oluşturun; mevcut servinin ayarlarını değiştirmeyin.

## Güvenli kurulum

1. Render'da bu depodan, dal olarak yalnızca `codex-v83-gelistirme` seçili yeni
   bir Web Service oluşturun.
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `gunicorn --bind 0.0.0.0:$PORT app_v84_beta:app`
4. Health Check Path: `/healthz`
5. Aşağıdaki değişkenleri Render'ın gizli environment-variable alanına ekleyin.
   Değerleri repoya, dokümana, komuta veya ekran görüntülerine koymayın.
6. Test URL'sini yalnızca beta katılımcılarıyla paylaşın. Uygulama HTTP Basic
   Auth gerektirir; kullanıcı adı ve parolayı ayrı güvenli kanallardan iletin.

## Gerekli ortam değişkenleri

| Değişken | Açıklama |
| --- | --- |
| `FOOTBALL_DATA_API_KEY` | football-data.org API anahtarı; maç ve geçmiş verisi için zorunlu. |
| `BETA_USERNAME` | Beta HTTP Basic Auth kullanıcı adı; zorunlu. |
| `BETA_PASSWORD` | Uzun, rastgele beta parolası; zorunlu. |
| `PORT` | Render tarafından atanır; elle tanımlamayın. |

Kimlik bilgileri eksikse korumalı beta sayfaları `503` döndürür; uygulama
güvenli biçimde veri göstermez. Yanlış veya eksik kimlik bilgileri `401`
döndürür. `/healthz` yalnızca servis durumunu bildirir, maç veya tahmin verisi
içermez.

## Beta davranışı

- Günlük liste gerçek football-data.org verisinden gelir.
- Detay ekranı yalnızca korumalı V8 analizi başarılıysa olasılıkları gösterir.
- Desteklenmeyen lig, geçmiş başlama saati veya yetersiz geçmiş veri için
  sentetik/örnek tahmin gösterilmez; kullanıcıya veri yeterliliği uyarısı
  gösterilir.
- Tahminler bilgilendirme amaçlıdır; bahis tavsiyesi veya sonuç garantisi
  değildir.
