# ali — Atlas Coffee / Stok Yönetim Sistemi

> Claude Code'un her oturumda okuduğu proje hafızası.
>
> **Kural: her oturumun sonunda bu dosyayı güncelle.** Yapı değiştiyse ilgili
> bölümü düzelt, yapılan işi en alttaki **Değişiklik günlüğü**'ne bir satırla ekle.
> Gelecek oturum neyin neden böyle olduğunu buradan öğreniyor.

---

## ⚠️ ÖNCE BUNU OKU: Proje CANLIDA çalışıyor

Atlas Kırtasiye'nin gerçek kasası. Yanlış bir değişiklik dükkânı durdurur.
Sunucudaki repo: `/home/barkod`

### Deploy — sadece bu üç komut

```bash
cd /home/barkod
git pull
docker compose up -d --build
docker compose run app_barkod python manage.py collectstatic --noinput
```

Bu kadar. Sırasıyla:
1. `git pull` — kodu getirir. `docker-compose.yml` çalışma dizinini konteynere
   bağladığı için (`.:/srv/app_barkod`) kod anında içeride olur.
2. `docker compose up -d --build` — konteyner yeniden başlar. `entrypoint.sh`
   açılışta **`migrate --noinput`** çalıştırır, bekleyen migration'ları kendisi uygular.
   Sadece `git pull` yetmez: çalışan gunicorn eski kodu hafızasında tutar.
3. `collectstatic` — `entrypoint.sh` bunu çalıştırmaz, elle gerekir (aşağıya bak).

### ❌ `makemigrations` ÇALIŞTIRMA

Migration dosyaları repoda; `migrate` onları zaten uyguluyor. `makemigrations`
yazarsan Django `stok/0009_alter_musteri_cep_telefonu.py` üretir — canlı müşteri
tablosuna dokunan, planlamadığın bir değişiklik.

**Sebebi:** `stok/models.py` `Cep_Telefonu` alanını `null=True` diyor ama migration
`0008` NOT NULL bırakmış. Yıllardır duran bir uyumsuzluk, bizim açtığımız değil.
Değişikliğin kendisi zararsız (PostgreSQL'de `DROP NOT NULL`, anlık, veri kaybı yok)
ama bilerek ve ayrı bir zamanda yapılmalı.

Yeni bir model alanı eklersen migration'ı **burada** üret (`makemigrations kahve`),
commit'le, sunucu sadece `migrate` etsin.

### `collectstatic` neden şart
`entrypoint.sh` sadece `migrate` çalıştırıyor. `kahve` sayfaları CSS'ini
`{% static 'kahve/kahve.css' %}` ile yüklüyor; dosya `STATIC_ROOT`'a ancak
`collectstatic` ile kopyalanır. Çalıştırılmazsa `/kahve/` sayfaları **stilsiz** açılır.

### Deploy sonrası ilk işler
1. **Admin → Kahve Ayarları** → "Günlük cron adresi"ni kopyala, PHP sitendeki
   gece 02:00 cron'una koy. Süresi dolan damgaları o düşürür.
2. **Admin → Kahveler** → ürünlere fotoğraf yükle ve **"Hediye sayacına +1"**
   kutusunu işaretle — varsayılan kapalı gelir, işaretlenmezse damga vermez.
3. **Stok takibi isteğe bağlı:** Admin → Stok ürünleri → takip etmek istediğin
   ürünün **Stok adedi** alanını doldur. Boş bırakılanlar eskisi gibi çalışır.

### Ters giderse
```bash
git revert <commit>          # ya da: git reset --hard <eski-commit>
docker compose up -d --build
```
`kahve` tabloları yeni ve `stok` onlara hiç dokunmuyor; kalsalar da zarar vermezler.
Veri kaybı riski yok.

### Yedek almadan büyük değişiklik yapma
`/admin/stok/stok/` → tümünü seç → **"Seçili ürünleri CSV olarak indir (yedek)"**.
Detay: aşağıdaki "Yedekleme / geri yükleme" bölümü.

### Kod kuralları
- Mevcut migration dosyalarını **asla** düzenleme veya silme. Sadece yeni ekle.
- Yıkıcı migration (`RemoveField`, `DeleteModel`, alan daraltma) önce kullanıcıya sorulur.
- `ali/settings.py` ve `ali/urls.py` değişiklikleri küçük ve geri alınabilir olsun.

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
python3 manage.py test stok kahve     # 196 test (73 stok + 123 kahve)
cd mobilapp && flutter analyze && flutter test    # 4 test
```

---

## App'ler

### `stok` — mevcut kırtasiye sistemi

Barkodlu stok, sepet, müşteri borç takibi, fiyat monitörü. Fonksiyon tabanlı view'lar,
template'ler `templates/system/user/` altında.

#### Sayfalar
| URL | Ne | Tasarım |
|---|---|---|
| `/` | Halka açık ana sayfa ("tek dükkân, iki tezgâh") | Atlas (yeni) |
| `/giris-yap/` | Personel girişi | Atlas (yeni) |
| `/panel/` | Gösterge paneli — açık borç, bugünün özeti, listeler | Atlas (yeni) |
| `/modern-urun-ara/` | Kırtasiye kasası | eski Bootstrap teması |
| `/musteri-listesi/` | Müşteriler — arama, borca/isme göre sıralama, toplam borç | Atlas (yeni) |
| `/bakiye/...`, `/urun-ara*` | diğer ekranlar | eski Bootstrap teması |
| `/fiyat-monitor/` | Halka açık fiyat sorgulama (login yok) | kendi tasarımı |

**Ortak footer:** `templates/parcali/site_footer.html` — hem Atlas hem kahve
sayfalarında. İçinde SEO backlink'leri var (cocukmasallarioku, enguzelsiirler,
erkekbebekisimleri, yuksekteknoloji); eski footer'dan taşındı, silme.
Uygulama ekranlarında (panel, giriş, kasa) `{% block alt_bilgi %}{% endblock %}`
ile kapatılıyor.

**Tasarım geçişi yarım:** `/`, `/giris-yap/`, `/panel/` ve `/musteri-listesi/` yeni **Atlas** tasarım
sistemine geçti (`stok/static/stok/atlas.css`, `.at` sınıfı altında kapsanmış,
`templates/system/user/atlas_base.html`'i genişletir). Kalan sayfalar hâlâ eski
`userBase.html` + Bootstrap temasında. Sıradaki adım onları taşımak.

Atlas, kahve modülünün kardeşi: aynı tipografi, aynı 8pt ızgara, aynı yuvarlaklık.
Fark renkte — kahve sıcak amber ekseninde, kırtasiye serin çini mavisi ekseninde.

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

#### Satış kaydı, stok adedi ve kasa raporu (2026-08-30'da eklendi)

Kırtasiye tarafında **hiç satış kaydı yoktu** — sepet sadece siliniyordu, ne kadar
nakit ne kadar kart girdiği hiçbir yerde yazmıyordu. Üç yeni model bunu kapatıyor:

| Model | Ne tutuyor |
|---|---|
| `Satis` | Tamamlanan satış: toplam, nakit, kart, **borç tutarı**, ödeme türü, kasiyer |
| `SatisSatiri` | Satırdaki ürün + **o anki fiyat** (sonra zam yapılsa da geçmiş bozulmaz) |
| `StokHareketi` | Adedi değiştiren her olay: satış, mal girişi, sayım düzeltmesi, iade |

**Stok adedi isteğe bağlı.** `Stok.stok_adedi` **boş bırakılırsa o ürün takip
edilmez** — binlerce ürünün sayımı bir günde yapılamaz. Sadece takip etmek
istediğin ürüne adet gir; gerisi eskisi gibi çalışır. Adet doluysa satışta düşer
ve `StokHareketi` yazılır.

**Özel indirim** (`stok/indirim.py` — **iki tezgâh da bunu kullanıyor**, oturum
anahtarları ayrı: `ANAHTAR` / `KAHVE_ANAHTAR`): kasada sepetin tamamına TL ya da yüzde
indirim verilebilir. Oturumda tutulur, **satış bitince temizlenir** — yarım kalan
indirim bir sonraki müşteriye taşınmaz. Ara toplamı aşamaz, eksiye düşüremez.
`Satis.indirim_tutari` kayda geçer; `toplam` indirim **düşülmüş** tutardır, yani
raporda ciro gerçekte alınan paradır. `ara_toplam` özelliği ikisini toplar.

> **Tuzak:** site Türkçe yerelleştirmede, `floatformat` ondalık ayracı **virgül**
> basıyor. JS `parseFloat` virgüllü sayıda kuruşu yutuyor; `sepetToplam`
> değişkenine `stringformat:".2f"` ile **noktalı** değer veriliyor.

Kasada iki buton var (`/modern-urun-ara/`):
- **Satışı Tamamla** → nakit / kredi kartı / parçalı. Parçalıda nakit+kart toplamı
  tutara eşit olmak zorunda, **sunucu da doğruluyor**.
- **Borça Aktar** → tümü ya da parçalı. Parçalıda kalan kasaya nakit yazılır.
  Açıklamaya o gün alınanlar ve varsa personelin yazdığı not düşer.

**Kasa raporu `/kasa-raporu/`** (`stok/rapor.py`): gün / ay / yıl, iki tezgâhı
birleştirir. Borca yazılan tutar **ciroya dahil ama kasaya girmez** — o yüzden
"nakit + kart" ile ciro birbirini tutmaz, ikisi ayrı gösterilir. Sayfada ayrıca
gün gün ciro grafiği, satış hareketleri, stok hareketleri ve azalan ürünler var.

> **Tuzak:** `makemigrations stok` çalıştırırsan Django yanına
> `Musteri.Cep_Telefonu` için planlanmamış bir `AlterField` daha üretir. Üretilen
> dosyadan **o operasyonu elle sil** — `0009` ve `0010`'da böyle yapıldı, ikisinin
> de docstring'inde yazıyor. `makemigrations kahve` bile `stok.Musteri`'ye FK
> eklendiği için aynı şeyi üretebiliyor.

#### Yedekleme / geri yükleme (asıl değerli veri burada)
**En pratik yol — admin'den indir:** `/admin/stok/stok/` → üstteki kutuyu işaretle →
"Tümünü seç" → Eylem: **"Seçili ürünleri CSV olarak indir (yedek)"**. Aynı eylem
grup ekranlarında da var. İnen dosya `stok_ice_aktar` ile geri yüklenebilir.

> **Tuzak:** `HttpResponse(content_type="...charset=utf-8-sig")` yazma. Django o
> durumda **her `write()` çağrısında** BOM ekler, dosya geri yüklenemez hale gelir.
> Charset `utf-8` olacak, BOM bir kere elle yazılacak. `stok/tests.py` bunu koruyor.

Sunucuda komutla:
```bash
python manage.py stok_disa_aktar                        # yedek/stok-<tarih>/ oluşturur
python manage.py stok_ice_aktar yedek/.../urunler.csv            # kuru çalışma
python manage.py stok_ice_aktar yedek/.../urunler.csv --uygula   # gerçekten uygular
python manage.py loaddata yedek/.../tum-veri.json                # birebir geri yükleme
```

Yedek klasörü: `urunler.csv` (Excel'de açılır — barkod, ad, fiyat, gruplar),
`liste-gruplari.csv`, `urun-gruplari.csv`, `tum-veri.json`.

- Ürünler **barkoda göre** eşleşir; aynı barkod varsa güncellenir, kopya üretmez.
- Eksik gruplar otomatik açılır. Yan dosyalar da okunduğu için **hiç ürünü olmayan
  gruplar da geri gelir**.
- **`bulk_create` kullanma:** `Stok.save()` arama alanı `Urun_Genel`'i hesaplıyor,
  toplu ekleme onu atlar ve ürün araması sessizce bozulur. `stok/tests.py` bunu koruyor.
- Varsayılan kuru çalışma; `--uygula` vermeden hiçbir şey değişmez.

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

#### Kategoriler
`KahveKategori` — menü bölümü (Sıcak İçecekler, Soğuk İçecekler, Ekstralar...).
Admin'den yenisi eklenebilir; menü, kasa ekranı ve mobil uygulama kendiliğinden
yeni bölümü gösterir. Kategorisi olmayan ürünler "Diğer" başlığı altında çıkar.

Menüyü tek seferde kurmak için (`kahve/menu_verisi.py`):
```bash
python manage.py kahve_menu_yukle                    # ne olacağını gösterir
python manage.py kahve_menu_yukle --uygula           # ekler
python manage.py kahve_menu_yukle --uygula --kahvelere-damga   # kahvelerde +1 açık gelsin
```
Tekrar çalıştırılabilir: var olan ürünlerin **sadece** fiyatı, sırası ve kategorisi
güncellenir. İşaretlenmiş "+1" kutusu, yüklenen görsel ve yazılan açıklama korunur.

> Personel ekranındaki "Menüyü yükle" sayfası **2026-08-30'da kaldırıldı** —
> menü bir kere yüklendi, tekrar gerekmiyor. `MenuYuklemeTesti` geri gelmemesini
> kilitliyor.

#### Görseller 1:1
Menü, ana sayfa ve mobil uygulama görselleri **kare** gösteriyor. Yüklenen fotoğraf
merkezden kare kırpılıp en fazla 1200px'e küçültülüyor (`Kahve._gorseli_kucult`),
böylece kırpma bir kez yapılıyor ve her ekranda aynı kare görünüyor.

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
4. **Özel indirim** sepetin altında: TL ya da yüzde. **Hediyeler düşüldükten
   sonraki** tutara uygulanır — bedava verilen fincandan ayrıca indirim yapılmaz.
   Kasa sıfırlanınca ve satış bitince temizlenir. `KahveSatis.indirim_tutari`
   kayda geçer, `toplam` indirimli tutardır.
5. Ödeme: **nakit / kredi kartı / parçalı / borca yaz**. "Borca yaz" kırtasiye
   tarafındaki müşteri listesini açar (`/kahve/kasa/borc-musterileri/`); seçilen
   müşterinin **aynı borç hanesine** işler, `BorcHareketi` açıklamasına alınan
   kahveler ve varsa not yazılır. İki tezgâh tek müşteri kaydını paylaşıyor. Parçalıda nakit+kart toplamı tutara eşit
   olmak zorunda — **sunucu da doğruluyor**, sadece JS değil.
   Tutar 0 ise (müşteri sadece hediyesini alıyor) ödeme türü sorulmaz; buton
   "Hediyeyi ver ve bitir"e döner ve satış doğrudan kapanır.
6. Satış bitince `KahveSatis` yazılır, müşteri varsa damgalar işlenir, **kasa sıfırlanır**.

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

#### Yedekleme / geri yükleme
```bash
python manage.py kahve_disa_aktar                       # yedek/kahve-<tarih>/ oluşturur
python manage.py kahve_ice_aktar yedek/.../urunler.csv           # kuru çalışma
python manage.py kahve_ice_aktar yedek/.../urunler.csv --uygula  # gerçekten uygular
python manage.py loaddata yedek/.../tum-veri.json                # her şeyi geri yükler
```

Yedek klasörü: `urunler.csv` (Excel'de açılır, fiyat toplu düzenlenebilir),
`tum-veri.json` (müşteriler/damgalar/satışlar dahil), `gorseller/`.
İçe aktarma ürünleri **ada göre** eşler — aynı ad varsa günceller, yoksa oluşturur,
yani kopya üretmez. Varsayılan kuru çalışma; `--uygula` vermeden hiçbir şey değişmez.

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
Sunucuya **ulaşılamazsa** yine demo gösterilir ama ekranda sarı bir uyarı şeridi
çıkar ("Sunucuya ulaşılamadı") — sessizce demo göstermek gerçek arızayı gizliyordu.

`AndroidManifest.xml` (main) içinde `INTERNET` izni **elle eklendi**; Flutter şablonu
onu sadece debug/profile manifest'lerine koyuyor, release derlemesi internete
çıkamıyordu. Silme. Debug manifest'inde ayrıca `usesCleartextTraffic` var —
`adb reverse tcp:8899 tcp:8899` ile bilgisayardaki yerel sunucuya bağlanıp test etmek
için; release'e sızmaz.

**Veri kaynağı:** menü ve ayarlar (hediye eşiği, işletme adı, geçerlilik günü)
sunucudan gelir. Kart verisi Firebase bağlanana kadar demodur — ama eşiği
sunucudaki gerçek kurala göre kurulur, yani damga sırası doğru sayıda çıkar.

**Ekranlar**
- `giris_ekrani` — tam ekran espresso fotoğrafı + tek buton
- `ana_ekran` — menü ve ayarları çeker, kategori filtresini tutar.
  Alt bar **cam (buzlu)** ama **sadece iki sekme**: Menü / Kartım.
  `extendBody: true` olduğu için içerik barın altından akar — listelerin
  alt boşluğu (`+92`) bu yüzden var, kaldırma.
- `menu_sekmesi` — üstte başlık, hemen altında **yatay kayan kategori şeridi**
  (`KategoriSeridi`, `parcalar/cam_bar.dart`), sonra ilerleme şeridi ve fotoğraflı
  kartlar. Bekleyen hediye varsa uygun kahveler "HEDİYENLE ALABİLİRSİN" rozeti alır.
  Kategoriler alt bara **konmaz** — navigasyon ile filtre ayrı şeyler, karıştırıldığında
  kullanıcı "alttaki navigasyon daha kötü oldu" diye geri bildirim verdi.
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

---

## Değişiklik günlüğü

> Her oturumda buraya ekle. Yeni kayıt en üste.

### 2026-08-31
- **Özel indirim** — **iki kasada da** sepete TL ya da yüzde indirim. Satış, borç
  ve rapor indirimli tutarı kullanıyor; satış bitince ve kasa sıfırlanınca
  temizleniyor. Kahvede indirim hediyeler düşüldükten sonraki tutara uygulanıyor.
- **Sepette kalan stok** — adet alanının altında "Stok: 16"; yetersiz ve tükenmiş
  durumlar kırmızı rozet. Adedi boş bırakılan ürün için hiçbir şey yazılmıyor.
- **Borç ekranı Atlas'a taşındı** — `/bakiye/` ve `/bakiye-hareketi/` tek sayfa
  oldu; her hareket +/- yönü ve işlem sonrası bakiyeyle görünüyor.
- **`/bakiye-hareketi/` 500 veriyordu** — iki view de sadece POST'a cevap
  veriyordu, GET'te `None` dönüyordu.
- **Güvenlik: 16 view'da `login_required` yoktu** — `/borc-duzenle/` müşterinin
  borcunu, `/fazlalik-sil/` ürünü dışarıdan gelen düz bir POST ile
  değiştirebiliyordu. Dekoratör `@csrf_exempt`'in **altına** eklendi.
- **Güvenlik: para uçlarında CSRF muafiyeti kaldırıldı** — `/api/satis-tamamla/`
  ve `/api/borca-aktar/`. Sayfa artık `X-CSRFToken` gönderiyor.
- **Sıralama** — kategori sırası + kategori içi ürün sırası zaten çalışıyordu,
  testle kilitlendi. Sırası boş yeni ürün artık kategorinin **sonuna** gidiyor
  (başa zıplıyordu); kategorisiz ürün için `nulls_last` yazıldı, SQLite ile
  PostgreSQL farklı sıralıyordu.
- **Kasa raporuna tezgâh dökümü** — nakit/kart/borç kırılımı kırtasiye ve kahve
  için ayrı ayrı.

### 2026-08-30 (ikinci oturum)
- **Kasa ekranı bozuktu, düzeltildi** — `templates/kahve/kasa.html` içinde
  sepet/müşteri/ödeme panelinin HTML'i **hiç yazılmamıştı**; JS `khSatirlar`,
  `khToplam`, `khOdemeAc` gibi olmayan elemanları arıyordu. Ürün butonları da
  CSS'i olmayan `.kh-sec` sınıflarını kullanıyordu (o yüzden düz beyaz etiket
  görünüyorlardı). Testler sadece JSON uçlarını sınadığı için görmemişti;
  `KasaSayfasiTesti` artık JS'in aradığı **her id'yi** sayfada arıyor.
- **Kasa ekranına kare ürün fotoğrafları** ve sağda yapışkan sepet paneli.
  Ekran artık dar kapsayıcı yerine 1520px kullanıyor.
- **Kırtasiye satışları kaydediliyor** — `Satis`, `SatisSatiri`, `StokHareketi`.
  Öncesinde sepet sadece siliniyordu, hiçbir yerde satış kaydı yoktu.
- **Stok adedi** (`Stok.stok_adedi`) — boş bırakılan ürün takip edilmez.
- **Kasa raporu `/kasa-raporu/`** — gün/ay/yıl, nakit/kart/borç kırılımı,
  iki tezgâh birlikte, gün gün ciro grafiği, satış ve stok hareketleri.
- **Kahve kasasına "Borca yaz"** — kırtasiye müşteri listesi kahve tarafında da
  kullanılıyor, aynı borç hanesine işliyor.
- **Borça Aktar penceresi yeniden tasarlandı** — sepet özeti, borç rozetli müşteri
  listesi, segment butonlu tip seçimi, **not alanı**. Açıklamaya o gün alınanlar
  yazılıyor (`BorcHareketi.aciklama` artık `TextField`).
- **Menüyü yükle ekranı kaldırıldı** — menü bir kere yüklendi, tekrar gerekmiyor.
- **Ana sayfa** — kahraman alan tam boy oldu (önce ince bir şerit gibiydi),
  iki katmanlı perde, CTA butonları, iki tezgâh kartı simetrik, damga kartını
  anlatan yeni şerit.
- **`.gitignore` düzeltildi** — 17. satırdaki `lib/` (Python paketleri için)
  `mobilapp/lib/` ile de eşleşiyordu; **Flutter kaynak kodunun tamamı repoda
  değildi**. `/lib/` yapıldı.

### 2026-08-30
- **`kahve` modülü eklendi** — kahve satışı, damga kartı, hediye kahve. Kasa
  ekranı (sepet → müşteri kartı → nakit/kart/parçalı ödeme → kasa sıfırlanır),
  gece cron'u, mobil API. Ürünlerde iki ayrı bayrak: "Hediye sayacına +1"
  (varsayılan **kapalı**, kurabiye/su için) ve "Hediye ile alınabilir".
- **Flutter mobil uygulaması** (`mobilapp/`) — alt navigasyonlu Menü + Kartım,
  tam ekran QR. Firebase henüz bağlı değil.
- **Kasa sayfası hızlandırıldı** — sepet satırındaki 1000 seçenekli `<select>`
  kaldırıldı (30 ürünlük sepet 5,7 MB → 13 KB), `select_related` ile 37 → 7 sorgu.
- **Beyaz tema kaldırıldı** — `/urun-ara-beyaz/`, `white.html`, `WhiteAssetsPanel/`
  (14 MB). F2 artık Modern sayfaya, F8 kahve kasasına gidiyor.
- **`login_url='giris-yap'` düzeltildi** — o isimde URL yoktu, anonim ziyaretçi
  302 yerine 500 alıyordu. Artık gerçekten var.
- **Ana sayfa ve giriş ayrıldı** — `/` halka açık ana sayfa oldu, giriş
  `/giris-yap/`'a taşındı. Panel yeniden yazıldı: 3 ürün sayısı yerine açık borç,
  bugünün kahve cirosu, borç hareketleri, tükenen ürünler.
- **Yedekleme** — admin'den "CSV olarak indir" eylemi + `stok_disa_aktar` /
  `stok_ice_aktar` komutları (kahve tarafında da aynısı var).
- **Kullanılmayan tema dosyaları silindi** — 286 dosya, 6 MB. Yüklenmeyen
  eklentiler, kullanılmayan ikon fontları, tema demo görselleri. Silmeden önce
  şablon + CSS `url()` referansları tarandı; `icofont`, `apex`,
  `perfect-scrollbar`, `img/svg`, `img/png-icon` kullanıldığı için duruyor.
- **Kategoriler** — `KahveKategori` eklendi, menü/kasa/mobil hepsi gruplu.
  `kahve_menu_yukle` komutu 29 ürünlük gerçek menüyü tek seferde kuruyor.
- **Görseller 1:1** — yüklemede merkezden kare kırpılıyor, her ekranda kare.
- **Ortak footer** — `atlas_footer.html`, tüm halka açık Atlas sayfalarında.
- **Mobil uygulama gerçek veriye bağlandı** — menü ve ayarlar sunucudan.
  Release APK'da `INTERNET` izni yoktu, uygulama sessizce demo veriye düşüyordu;
  izin eklendi, sunucuya ulaşılamadığında artık ekranda uyarı çıkıyor.
- **Alt navigasyon 2 sekmeye döndü** (Menü / Kartım, cam efekt kalıyor),
  kategoriler ürün ekranının üstüne taşındı.
- **Marka adı "Atlas Coffee"** — `kahve/0006` veri migration'ı kayıtlı isim hâlâ
  "Atlas Kahve" ise yenisine çeviriyor; kullanıcı kendi isim yazdıysa dokunmuyor.
- **Güvenlik** — kasa ekranındaki XSS (müşteri adı Firebase displayName'den
  geliyordu, `innerHTML` ile basılıyordu), `urun_miktar_guncelle`'de eksik
  `login_required` ve kullanıcı filtresi, müşteri barkodunda `random` → `secrets`.
