# ali — Atlas Kahve / Stok Yönetim Sistemi

> Claude Code'un her oturumda okuduğu proje hafızası. **Yapı değiştiğinde güncelle.**

---

## ⚠️ ÖNCE BUNU OKU: Proje CANLIDA çalışıyor

Atlas Kırtasiye'nin gerçek kasası. Yanlış bir değişiklik dükkânı durdurur.

**Kurallar**
- Mevcut migration dosyalarını **asla** düzenleme veya silme. Sadece yeni migration ekle.
- Yıkıcı migration (`RemoveField`, `DeleteModel`, alan daraltma) önce kullanıcıya sorulur.
- `ali/settings.py` ve `ali/urls.py` değişiklikleri küçük ve geri alınabilir olsun.
- `makemigrations`'ı **app adı vererek** çalıştır (aşağıdaki drift notuna bak).

**Canlı deploy komutları**
```bash
docker compose run app_barkod python manage.py makemigrations kahve   # app adını ver!
docker compose run app_barkod python manage.py migrate
docker compose run app_barkod python manage.py collectstatic --noinput
docker compose up -d --build
```

### `collectstatic` neden şart
`entrypoint.sh` sadece `migrate` çalıştırıyor. `kahve` sayfaları CSS'ini
`{% static 'kahve/kahve.css' %}` ile yüklüyor; dosya `STATIC_ROOT`'a ancak
`collectstatic` ile kopyalanır. Çalıştırılmazsa `/kahve/` sayfaları **stilsiz** açılır.
Kullanıcı bunu biliyor, DEBUG'ı kapattığında yapacak.

### Bilinen drift (önceden var olan, bizim açmadığımız)
`stok/models.py` içindeki `Musteri.Cep_Telefonu` alanı `null=True` diyor ama son
migration (`0008`) NOT NULL bırakmış. Çıplak `makemigrations` `stok/0009...` üretir.
Teknik olarak güvenli (NOT NULL → NULL) ama plansız bir şema değişikliğidir.
Bilinçli yapılana kadar **`makemigrations kahve`** kullan.

---

## Ortam

| | |
|---|---|
| Django | 4.2.4 (üretim). Sistem python3'ünde 5.2 var — **onu kullanma** |
| Python | 3.10 |
| DB | PostgreSQL (üretim), `DATABASE_URL` ile |
| Ayarlar | `django-environ`, `ali/docker.env` (repoda yok) |
| Deploy | Docker Compose, servis adı `app_barkod` |
| Mobil | Flutter 3.38, `mobilapp/` |
| Yeni bağımlılık | **Yok.** `kahve` sadece `requests` + `Pillow` kullanıyor, ikisi de kurulu |

### Lokalde çalıştırma
Repodaki `venv/` bozuk (bin/ yok) ama içinde doğru Django 4.2.4 var:

```bash
cd /Users/melih/Desktop/Code/ali
export SECRET_KEY=yerel DEBUG=True \
       ALLOWED_HOSTS="localhost,127.0.0.1,testserver" \
       CSRF_TRUSTED_ORIGINS=http://localhost \
       DATABASE_URL="sqlite:///$PWD/yerel.sqlite3" \
       PYTHONPATH="$PWD/venv/lib/python3.10/site-packages"
python3 manage.py migrate
python3 manage.py runserver 0.0.0.0:8899
```

Yerel veritabanını repoya koyma. Yüklenen görseller `media/` altına düşer, `.gitignore`'da.

### Test
```bash
python3 manage.py test stok kahve     # 88 test (12 stok + 76 kahve)
cd mobilapp && flutter analyze && flutter test    # 4 test
```

---

## App'ler

### `stok` — mevcut kırtasiye sistemi

Barkodlu stok, sepet, müşteri borç takibi, fiyat monitörü. Fonksiyon tabanlı view'lar,
template'ler `templates/system/user/` altında.

**Kasa ekranı `/modern-urun-ara/`.**

Klavye kısayolları (iki kasada da aynı):
| Tuş | Ne yapar |
|---|---|
| F2 | Kırtasiye kasası (`/modern-urun-ara/`) |
| F3 | Bulunduğun kasanın sepetini sıfırlar |
| F4 | Müşteri listesi |
| F8 | Kahve kasası (`/kahve/kasa/`) |

F5/F7/F11/F12 tarayıcıya ait (yenile, caret browsing, tam ekran, geliştirici araçları) —
kullanmayın.

**Dikkat edilecek üç tuzak** (üçü de yaşandı, `stok/tests.py` koruyor):

1. **Miktar alanı `<input type="number">` olmalı.** Eskiden 1000 seçenekli `<select>` idi;
   satır başına ~190 KB HTML üretiyordu, 30 ürünlük sepet 5,7 MB olup tarayıcıyı
   kilitliyordu. `Sayi = range(1, 1001)` bağlamı bu yüzden kaldırıldı.
2. **Sepet sorgularında `select_related('urun')` şart**, yoksa her satır ek sorgu açar
   (30 üründe 37 → 7 sorgu farkı).
3. **`login_url` değeri `'home'`.** `'giris-yap'` diye bir URL adı yok; öyle yazılırsa
   anonim ziyaretçi 302 yerine `NoReverseMatch` → 500 alır.

**Kaldırılanlar (2026-08-30):** beyaz tema — `/urun-ara-beyaz/`, `white.html` ve
`WhiteAssetsPanel/` (14 MB, 469 dosya). F2 artık Modern sayfaya gidiyor.

**`yeni-sayfa`** hiçbir yerden link almıyor (öksüz). `*-beyaz` sepet uçları
(`sepete-ekle-beyaz`, `manuel-tutar-beyaz`, `sepeti-sifirla-beyaz`,
`sepet_urun_sil-beyaz`) sadece o sayfa tarafından kullanılıyor, o yüzden duruyorlar.
`yeni-sayfa` da kaldırılırsa bu 4 uç ve view'ları da silinebilir.

**Bilinen, henüz yapılmamış iyileştirmeler:** sepet işlemleri hâlâ tam sayfa yenilemesi
yapıyor; sayfa Tailwind'i CDN'den çekip tarayıcıda derliyor (konsol uyarı veriyor).

---

### `kahve` — kahve satış + sadakat modülü

```
kahve/
  models.py    KahveAyar (tekil), Kahve, KahveMusteri, KahveIcim, HediyeKahve, KahveSatis
  sadakat.py   Sadakat kuralları — iş mantığının TEK kaynağı
  kasa.py      Kasa sepeti (oturumda) + satış tamamlama
  firebase.py  Firebase ID token doğrulama (firebase-admin gerektirmez)
  views.py     Web sayfaları + kasa uçları + cron + mobil API
  admin.py     Tüm yönetim buradan
  management/commands/gorsel_temizle.py
templates/kahve/   base, menu, kart (personel görünümü), kasa
                   base.html'de `{% block ust_nav %}` var: varsayılan müşteri
                   navigasyonu, kasa.html personel navigasyonuyla eziyor
kahve/static/kahve/kahve.css
```

#### Ürün bayrakları (`Kahve` modeli) — karıştırma, ikisi ayrı eksen
| Alan | Admin etiketi | Varsayılan | Ne yapar |
|---|---|---|---|
| `damga_veriyor` | Hediye sayacına +1 | **False** | Satılınca sayaca damga ekler |
| `hediye_gecerli` | Hediye ile alınabilir | True | Hediyeyle bedava verilebilir |

Kurabiye/su → ikisi de kapalı. Kahve → `damga_veriyor` **açılmalı**, yoksa damga vermez.
Varsayılan False çünkü menüye kahve dışı ürün eklemek daha sık; yanlışlıkla hediye
kazandırmasın. Migration `0003` mevcut ürünleri `True` yapar — o alan eklenmeden önce
her ürün damga veriyordu, sessizce durmasın diye.

Damga vermeyen ürün yine de `KahveIcim` olarak yazılır ama `durum=sayilmaz` ile;
geçmişte görünür, sayaca girmez.

#### Sadakat kuralı (`sadakat.py` — mantığı değiştireceksen sadece burayı değiştir)
- Damga veren her ürün bir `KahveIcim` açar, `son_gecerlilik = tarih + gecerlilik_gun`.
  **Adet kadar damga düşer**: tek satışta 6 kahve alan 6 damga kazanır.
- Sayaçta `hediye_icin_kahve` adet birikince **en eski**ler harcanır, 1 `HediyeKahve` yazılır.
- Süresi dolan kayıt `durum=doldu` olur, sayaçtan düşer (5 → 4). Silinmez, geçmiş korunur.
- Hediye kahve `durum=hediye` ile kaydedilir; yeni sayacı **başlatmaz**, süresi de dolmaz.
- Eşik ve gün sayısı admin'den ayarlanır, değişiklik anında geçerli olur.
- Süre kontrolü iki yerden çalışır: gece cron'u (tüm müşteriler) + kart okunduğu an
  (tek müşteri). Cron bir gün çalışmasa bile ekrandaki sayı doğru kalır.

#### Kasa akışı (`kasa.py`)
1. Soldan kahveye tıkla → sepete girer. Sepet **oturumda** tutulur; satış bitene kadar
   veritabanına hiçbir şey yazılmaz (yarım kalan satış çöp kayıt bırakmaz).
2. Müşteri kartı barkod/QR ile okutulur — **isteğe bağlı**, kartsız satış da olur.
3. Bekleyen hediyesi varsa satırda "Hediye kullan" çıkar, tutardan düşer.
   `hediye_gecerli=False` olan kahveler hediye olarak verilemez.
4. Ödeme: **nakit / kredi kartı / parçalı**. Parçalıda nakit+kart toplamı tutara eşit
   olmak zorunda — **sunucu da doğruluyor**, sadece JS değil.
   Tutar 0 ise (müşteri sadece hediyesini alıyor) ödeme türü sorulmaz; buton
   "Hediyeyi ver ve bitir"e döner ve satış doğrudan kapanır.
5. Satış bitince `KahveSatis` yazılır, müşteri varsa damgalar işlenir, **kasa sıfırlanır**.

Kartsız satışta `KahveIcim` yazılmaz (müşteri yok), sadece `KahveSatis` kaydedilir.
Günlük ciro/nakit/kart özeti ekranın sağ üstünde (`kasa.gunun_ozeti()`).
Kasa uçlarının hepsi JSON döner — **sayfa hiç yenilenmez**.

#### URL'ler
| URL | Kim |
|---|---|
| `/kahve/` | Halka açık menü |
| `/kahve/k/<uuid>/` | **Personel** — admin'den bir müşterinin kartını açar |
| `/kahve/kasa/` | **Personel** — kasa ekranı |
| `/kahve/kasa/...` | **Personel** — sepet/müşteri/ödeme uçları, hepsi JSON |
| `/kahve/cron/gunluk-temizlik/?anahtar=...` | Cron (anahtarla) |
| `/kahve/api/v1/...` | Mobil uygulama (`X-Kahve-Key`) |

#### Anahtarlar (ikisi de admin > Kahve Ayarları'nda, kodda sabit yok)
- `cron_anahtari` → cron URL'inde `?anahtar=`
- `mobil_api_anahtari` → mobil uygulamada **`X-Kahve-Key`** başlığında

Müşteri barkodu `secrets` ile üretilir (kasada kimlik yerine geçiyor, tahmin edilebilir
olmamalı). QR jetonu ve anahtarlar `uuid4`.

#### Firebase — SADECE mobil uygulamada
**Kural: web sitesinde müşteri girişi ve müşteri ekranı YOKTUR.** Müşteri hesapları
yalnızca mobil uygulamada (Firebase) yaşar. Web'de sadece halka açık menü ve
personel ekranları vardır; personel girişi **sadece Django auth** ile (`/` → `views.home`).

2026-08-30'da kaldırıldı: `/kahve/giris/`, `/kahve/kart/`, `/kahve/oturum-ac/`,
`/kahve/cikis/`, `giris.html` ve `request.session["kahve_musteri_id"]` oturumu.
`MusteriWebeGiremezTesti` bunu kilitliyor — geri eklemeyin.

`KahveMusteri`, `django.contrib.auth.User`'dan bağımsız bir modeldir; müşterinin
Django kullanıcısı hiç yoktur, `staff_member_required`'ı geçemez.

`kahve/firebase.py` **duruyor**: mobil API'nin (`/api/v1/kart/`, `/api/v1/gecmis/`,
`/api/v1/oturum/`) token doğrulaması için gerekli. Doğrulama Google Identity Toolkit
`accounts:lookup` ile yapılır — `firebase-admin` paketi gerekmez, `requests` yeterli.
Admin'deki Firebase alanları da mobil uygulamaya servis edilir.

#### Görsel yönetimi
| Ne olur | Sonuç |
|---|---|
| Büyük fotoğraf yüklenir | En fazla **1400px**'e küçültülür (4000px/1,8 MB → 1400px/88 KB) |
| Ürünün görseli değiştirilir | Eski dosya diskten **silinir** |
| Ürün silinir | Görseli de **silinir** — toplu silmede de (`post_delete` sinyali) |

```bash
python manage.py gorsel_temizle          # öksüz dosyaları listeler (güvenli)
python manage.py gorsel_temizle --sil    # gerçekten siler
```

> **Dikkat:** komut, dosyaları **hangi veritabanına bakıyorsa** onunla karşılaştırır.
> Yanlış `DATABASE_URL` ile (ör. boş yerel db) çalıştırırsan bütün görseller öksüz
> görünür. `--sil` vermeden önce listeye bak — varsayılanın kuru çalışma olması bu yüzden.

`ali/urls.py` içinde `/media/` için **DEBUG'dan bağımsız** servis rotası var; DEBUG
kapatılınca da fotoğraflar çalışır. Önünde `/media/` location'ı olan nginx varsa istek
Django'ya hiç ulaşmaz. Görsel yine de yüklenemezse şablonlar halka motifine düşer.

---

### `mobilapp/` — Flutter

```
lib/
  tema.dart          tasarım belirteçleri (web CSS ile aynı değerler)
  demo_veri.dart     sunucu tanımlı değilken kullanılan örnek veri
  parcalar/          damga_halkasi.dart (imza bileşeni), kahve_gorseli.dart
  ekranlar/          giris_ekrani, ana_ekran (alt navigasyon),
                     menu_sekmesi, profil_sekmesi, okut_sayfasi (tam ekran QR)
  servis/            api.dart (X-Kahve-Key), yapilandirma.dart
  modeller/          kart.dart
assets/gorseller/    Unsplash kahve fotoğrafları (ücretsiz lisans, ~770 KB)
```

Sunucuya bağlamak:
```bash
flutter run --dart-define=KAHVE_SUNUCU=https://site.com \
            --dart-define=KAHVE_ANAHTAR=<mobil api anahtarı>
```
Tanımlı değilse `demo_veri.dart` kullanılır, uygulama boş ekran göstermez.

**Ekranlar**
- `giris_ekrani` — tam ekran espresso fotoğrafı + tek buton
- `ana_ekran` — alt navigasyon (Menü / Kartım). `Kart` durumu **burada** tutulur,
  iki sekme de aynı veriyi görür.
- `menu_sekmesi` — fotoğraflı kartlar + üstte ilerleme şeridi. Bekleyen hediye varsa
  uygun kahveler "HEDİYENLE ALABİLİRSİN" rozeti alır.
- `profil_sekmesi` — sadakat kartı + "Kasada okut" + sayaçlar
- `okut_sayfasi` — tam ekran beyaz QR/barkod. Akışın içine büyük beyaz panel koyma.

**`DamgaSirasi`** genişliğe göre kendini ölçer ve **tek sırada** kalır. Dar yerlerde
`enKucuk`/`enBuyuk` ile sınırla — sabit `olcu` verirsen taşar.

**Firebase henüz bağlı değil.** `giris_ekrani.dart` içindeki `_girisYap` doğrudan ana
ekrana geçiyor; Firebase eklenince orada token alınıp `KahveApi.oturumAc(idToken)`
çağrılacak. `/api/v1/kart/` ve `/api/v1/gecmis/` Firebase token'ı ister;
`/api/v1/menu/` ve `/api/v1/ayarlar/` sadece `X-Kahve-Key` ile çalışır.

---

## Tasarım dili

Kahve dükkânının kendi dünyasından: dijitalleşen şey **damga kartı**. İmza bileşen =
**kahve halkası damgası** — her fincan bir halka bırakır, altında tarihi ve karttan
düşmesine kalan gün. Süresi yaklaşan damga kırmızıya döner. Kural ekranda görünür bir
bilgi, gizli bir cron değil.

| | |
|---|---|
| Espresso | `#1C1411` `#261B16` `#33251E` |
| Krema (amber) | `#D69A4C` `#F1C68C` |
| Çini mavisi | `#2E6B78` `#59A0AC` |
| Porselen | `#F2F1EE` |
| Uyarı | `#C9563B` |

Tipografi: **Bricolage Grotesque** (başlık) / **Instrument Sans** (metin) /
**JetBrains Mono** (tarih, sayı, barkod). 8pt grid, radius 12/16/24, yumuşak gölgeler.

CSS `.kh` sınıfı altında kapsanmıştır — `stok` sayfalarını etkilemez.

---

## Dil

Kod, değişken ve fonksiyon adları **Türkçe** (`kahve_ekle`, `suresi_dolanlari_dusur`).
Python kaynak dosyalarındaki **yorumlarda Türkçe karakter kullanma** (bazı ortamlarda
bozuluyor). Buna karşılık **kullanıcının gördüğü her metinde tam Türkçe kullan** —
`verbose_name`, `help_text`, admin etiketleri, şablonlar, hata mesajları.
