import os
import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.db.models import F
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone


def _musteri_kodu_uret():
    """Barkod okuyucuya uygun 12 haneli sayisal musteri kodu.

    Kod kasada kimlik yerine geciyor; tahmin edilebilir olmamasi icin
    `random` degil `secrets` kullanilir.
    """
    while True:
        kod = "899" + "".join(secrets.choice("0123456789") for _ in range(9))
        if not KahveMusteri.objects.filter(kod=kod).exists():
            return kod


def _anahtar_uret():
    return uuid.uuid4().hex


class KahveAyar(models.Model):
    """Tek satirlik ayar tablosu. Admin panelinden yonetilir."""

    isletme_adi = models.CharField(max_length=120, default="Atlas Coffee", verbose_name="İşletme adı")
    slogan = models.CharField(
        max_length=200, blank=True, default="Beş kahve içenin altıncısı bizden", verbose_name="Slogan"
    )

    hediye_icin_kahve = models.PositiveIntegerField(
        default=5,
        verbose_name="Hediye için gereken kahve",
        help_text="Kaç kahve içince 1 kahve hediye olsun?",
    )
    gecerlilik_gun = models.PositiveIntegerField(
        default=30,
        verbose_name="Kahve geçerlilik süresi (gün)",
        help_text="İçilen bir kahve kaç gün boyunca hediye sayacında kalsın? Süre dolunca sayaçtan düşer.",
    )

    firebase_api_key = models.CharField(max_length=200, blank=True, verbose_name="Firebase Web API Key")
    firebase_auth_domain = models.CharField(max_length=200, blank=True, verbose_name="Firebase Auth Domain")
    firebase_project_id = models.CharField(max_length=200, blank=True, verbose_name="Firebase Project ID")
    firebase_app_id = models.CharField(max_length=200, blank=True, verbose_name="Firebase App ID")
    firebase_sender_id = models.CharField(max_length=200, blank=True, verbose_name="Firebase Sender ID")
    firebase_storage_bucket = models.CharField(max_length=200, blank=True, verbose_name="Firebase Storage Bucket")

    cron_anahtari = models.CharField(
        max_length=64,
        default=_anahtar_uret,
        verbose_name="Cron anahtarı",
        help_text="Günlük temizlik URL'inde kullanılır. Kimseyle paylaşma.",
    )
    mobil_api_anahtari = models.CharField(
        max_length=64,
        default=_anahtar_uret,
        verbose_name="Mobil API anahtarı",
        help_text="Mobil uygulama her istekte 'X-Kahve-Key' başlığında bu değeri gönderir.",
    )

    guncelleme_tarihi = models.DateTimeField(auto_now=True, verbose_name="Güncelleme tarihi")

    class Meta:
        verbose_name = "Kahve Ayarı"
        verbose_name_plural = "Kahve Ayarları"

    def __str__(self):
        return self.isletme_adi

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # ayar satiri silinmesin
        pass

    @classmethod
    def al(cls):
        ayar, _ = cls.objects.get_or_create(pk=1)
        return ayar

    @property
    def firebase_hazir(self):
        return bool(self.firebase_api_key and self.firebase_auth_domain and self.firebase_project_id)

    def firebase_web_config(self):
        return {
            "apiKey": self.firebase_api_key,
            "authDomain": self.firebase_auth_domain,
            "projectId": self.firebase_project_id,
            "appId": self.firebase_app_id,
            "messagingSenderId": self.firebase_sender_id,
            "storageBucket": self.firebase_storage_bucket,
        }


class KahveKategori(models.Model):
    """Menu bolumu: Sicak Icecekler, Soguk Icecekler, Atistirmalik...

    Yenisini admin'den ekleyebilirsin; menu ve kasa ekrani kendiliginden
    yeni bolumu gosterir.
    """

    ad = models.CharField(max_length=80, unique=True, verbose_name="Kategori adı")
    sira = models.PositiveIntegerField(default=0, verbose_name="Sıralama")
    aktif = models.BooleanField(default=True, verbose_name="Menüde görünsün")

    class Meta:
        ordering = ("sira", "ad")
        verbose_name = "Kahve Kategorisi"
        verbose_name_plural = "Kahve Kategorileri"

    def __str__(self):
        return self.ad


class Kahve(models.Model):
    kategori = models.ForeignKey(
        KahveKategori,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="urunler",
        verbose_name="Kategori",
        help_text="Boş bırakılırsa menüde 'Diğer' başlığı altında görünür.",
    )
    ad = models.CharField(max_length=120, verbose_name="Kahve adı")
    aciklama = models.TextField(blank=True, verbose_name="Açıklama")
    icindekiler = models.TextField(blank=True, verbose_name="İçindekiler", help_text="Her satıra bir malzeme yaz.")
    fiyat = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Fiyat (₺)")
    gorsel = models.ImageField(upload_to="kahve/", blank=True, null=True, verbose_name="Görsel")
    sira = models.PositiveIntegerField(default=0, verbose_name="Sıralama")
    aktif = models.BooleanField(default=True, verbose_name="Menüde görünsün")
    damga_veriyor = models.BooleanField(
        default=False,
        verbose_name="Hediye sayacına +1",
        help_text="Açıksa bu ürün satıldığında müşterinin sayacına damga eklenir. "
        "Kurabiye, su gibi hediye kazandırmayan ürünlerde kapalı bırakın.",
    )
    hediye_gecerli = models.BooleanField(
        default=True,
        verbose_name="Hediye ile alınabilir",
        help_text="Kapatırsan bu ürün hediye olarak verilemez.",
    )
    eklenme_tarihi = models.DateTimeField(auto_now_add=True, verbose_name="Eklenme tarihi")

    class Meta:
        # nulls_last SART: kategorisiz urunde SQLite NULL'u basa,
        # PostgreSQL sona koyuyor. Acikca yazmazsak yereldeki sira
        # canlidakiyle ayni olmuyor.
        ordering = (F("kategori__sira").asc(nulls_last=True), "sira", "ad")
        verbose_name = "Kahve"
        verbose_name_plural = "Kahveler"

    def __str__(self):
        return self.ad

    @property
    def icindekiler_listesi(self):
        return [s.strip() for s in self.icindekiler.splitlines() if s.strip()]

    def save(self, *args, **kwargs):
        # Sira bos birakilmis yeni urun kategorisinin SONUNA gitsin.
        # Varsayilan 0 oldugu icin admin'den eklenen her yeni urun listenin
        # basina ziplayip mevcut sirayi bozuyordu.
        if self._state.adding and not self.sira:
            son = (
                Kahve.objects.filter(kategori=self.kategori)
                .order_by("-sira")
                .values_list("sira", flat=True)
                .first()
            )
            self.sira = (son or 0) + 1
        super().save(*args, **kwargs)
        self._gorseli_kucult()

    def _gorseli_kucult(self, en_fazla_genislik=1200):
        """Yuklenen fotografi kare kirpar, kucultur ve JPEG'e cevirir.

        Menu ve mobil uygulama gorselleri 1:1 gosteriyor; kirpmayi burada bir
        kez yaparsak her ekranda ayni kare gorunur. Kare kirpma merkezden.

        JPEG'e cevirmek sart: menu fotograflari fotografik icerik ve PNG olarak
        ~1,7 MB geliyorlardi. 30 urunluk menu mobilde 50 MB indiriyordu; ayni
        gorsel JPEG olarak ~150 KB. Eskiden "zaten kare ve yeterince kucuk"
        diye erken donuyordu, dosyaya hic dokunmuyordu.

        Hata olursa sessizce vazgecer: admin kaydi asla bu yuzden basarisiz olmasin.
        """
        if not self.gorsel:
            return
        try:
            from PIL import Image

            yol = self.gorsel.path
        except (ImportError, NotImplementedError, ValueError):
            return  # Pillow yok ya da uzak depolama kullaniliyor

        try:
            resim = Image.open(yol)
            resim.load()
        except (OSError, ValueError):
            return  # bozuk ya da desteklenmeyen dosya

        try:
            kenar = min(resim.width, resim.height)
            hedef = min(kenar, en_fazla_genislik)

            sol = (resim.width - kenar) // 2
            ust = (resim.height - kenar) // 2
            kucuk = resim.crop((sol, ust, sol + kenar, ust + kenar))
            if kenar != hedef:
                kucuk = kucuk.resize((hedef, hedef), Image.LANCZOS)

            # Saydamlik varsa beyaza yatir; JPEG alfa tasimiyor.
            if kucuk.mode in ("RGBA", "LA", "P"):
                kucuk = kucuk.convert("RGBA")
                zemin = Image.new("RGB", kucuk.size, (255, 255, 255))
                zemin.paste(kucuk, mask=kucuk.split()[-1])
                kucuk = zemin
            else:
                kucuk = kucuk.convert("RGB")
        except (OSError, ValueError):
            return
        finally:
            resim.close()

        yeni_yol = os.path.splitext(yol)[0] + ".jpg"
        try:
            kucuk.save(yeni_yol, format="JPEG", quality=82, optimize=True, progressive=True)
        except (OSError, ValueError):
            return

        if yeni_yol == yol:
            return

        # Uzanti degisti: alan degerini guncelle, eski dosyayi sil.
        # save() yerine update(): tekrar buraya girip yeniden sikistirmasin,
        # gorsel degisimi sinyali de bosuna tetiklenmesin.
        yeni_ad = os.path.splitext(self.gorsel.name)[0] + ".jpg"
        self.gorsel.name = yeni_ad
        if self.pk:
            Kahve.objects.filter(pk=self.pk).update(gorsel=yeni_ad)
        try:
            os.remove(yol)
        except OSError:
            pass


class KahveMusteri(models.Model):
    firebase_uid = models.CharField(max_length=128, unique=True, null=True, blank=True, verbose_name="Firebase UID")
    ad_soyad = models.CharField(max_length=150, verbose_name="Ad soyad")
    email = models.EmailField(blank=True, verbose_name="E-posta")
    telefon = models.CharField(max_length=32, blank=True, verbose_name="Telefon")
    kod = models.CharField(max_length=32, unique=True, default=_musteri_kodu_uret, verbose_name="Barkod no")
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name="QR anahtarı")
    aktif = models.BooleanField(default=True, verbose_name="Aktif")
    kayit_tarihi = models.DateTimeField(auto_now_add=True, verbose_name="Kayıt tarihi")
    son_gorulme = models.DateTimeField(null=True, blank=True, verbose_name="Son görülme")

    class Meta:
        ordering = ("-kayit_tarihi",)
        verbose_name = "Kahve Müşterisi"
        verbose_name_plural = "Kahve Müşterileri"

    def __str__(self):
        return f"{self.ad_soyad} ({self.kod})"

    def aktif_icimler(self):
        return self.icimler.filter(durum=KahveIcim.Durum.AKTIF).order_by("tarih")

    @property
    def aktif_kahve_sayisi(self):
        return self.aktif_icimler().count()

    @property
    def bekleyen_hediye_sayisi(self):
        return self.hediyeler.filter(durum=HediyeKahve.Durum.BEKLIYOR).count()

    @property
    def toplam_icim_sayisi(self):
        return self.icimler.exclude(durum=KahveIcim.Durum.HEDIYE).count()


class KahveIcim(models.Model):
    """Musterinin ictigi her fincan icin bir kayit."""

    class Durum(models.TextChoices):
        AKTIF = "aktif", "Sayacta"
        HARCANDI = "harcandi", "Hediyeye sayıldı"
        DOLDU = "doldu", "Süresi doldu"
        HEDIYE = "hediye", "Hediye kahve"
        SAYILMAZ = "sayilmaz", "Sayaca girmez"

    musteri = models.ForeignKey(
        KahveMusteri, on_delete=models.CASCADE, related_name="icimler", verbose_name="Müşteri"
    )
    kahve = models.ForeignKey(Kahve, on_delete=models.SET_NULL, null=True, blank=True, related_name="icimler")
    kahve_adi = models.CharField(max_length=120, blank=True, help_text="Kahve silinse de geçmiş bozulmasın diye.")
    fiyat = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    durum = models.CharField(max_length=16, choices=Durum.choices, default=Durum.AKTIF, verbose_name="Durum")
    tarih = models.DateTimeField(default=timezone.now, verbose_name="Tarih")
    son_gecerlilik = models.DateTimeField(null=True, blank=True, verbose_name="Son geçerlilik")
    ekleyen = models.CharField(max_length=150, blank=True, verbose_name="Ekleyen personel")
    satis = models.ForeignKey(
        "KahveSatis",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="icimler",
        verbose_name="Satış",
    )

    class Meta:
        ordering = ("-tarih",)
        verbose_name = "Kahve İçimi"
        verbose_name_plural = "Kahve İçimleri"
        indexes = [
            models.Index(fields=["durum", "son_gecerlilik"]),
            models.Index(fields=["musteri", "durum"]),
        ]

    def __str__(self):
        return f"{self.musteri.ad_soyad} - {self.kahve_adi or 'Kahve'}"

    def save(self, *args, **kwargs):
        if not self.kahve_adi and self.kahve_id:
            self.kahve_adi = self.kahve.ad
        super().save(*args, **kwargs)

    @property
    def kalan_gun(self):
        """Sayactan dusmesine kac gun kaldi. Sayacta degilse None."""
        if self.durum != self.Durum.AKTIF or not self.son_gecerlilik:
            return None
        fark = self.son_gecerlilik - timezone.now()
        return max(0, fark.days + (1 if fark.seconds else 0))


class KahveSatis(models.Model):
    """Kasada tamamlanan bir satış. Sepetteki her fincan bir KahveIcim olur."""

    class Odeme(models.TextChoices):
        NAKIT = "nakit", "Nakit"
        KART = "kart", "Kredi kartı"
        PARCALI = "parcali", "Parçalı"
        BORC = "borc", "Borca yazıldı"

    musteri = models.ForeignKey(
        KahveMusteri,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="satislar",
        verbose_name="Müşteri",
        help_text="Kartsız satışta boş kalır.",
    )
    # toplam = indirim DUSULDUKTEN sonraki tutar. Ara toplam icin: toplam + indirim_tutari
    toplam = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Toplam")
    indirim_tutari = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, verbose_name="İndirim",
        help_text="Kasada elle verilen özel indirim.",
    )
    nakit_tutar = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Nakit")
    kart_tutar = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Kredi kartı")
    odeme_turu = models.CharField(
        max_length=16, choices=Odeme.choices, default=Odeme.NAKIT, verbose_name="Ödeme türü"
    )
    borc_musteri = models.ForeignKey(
        "stok.Musteri",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kahve_satislari",
        verbose_name="Borç yazılan müşteri",
        help_text="Ödeme türü 'Borca yazıldı' ise dolu olur. Kırtasiye tarafındaki müşteri listesi.",
    )
    # Satista ne verildiginin metin ozeti. KahveIcim sadece kart okutuldugunda
    # yaziliyor; kartsiz satista ne satildigi baska hicbir yerde durmuyordu.
    urunler = models.CharField(max_length=255, blank=True, verbose_name="Satılanlar")
    fincan_adedi = models.PositiveIntegerField(default=0, verbose_name="Kalem adedi")
    hediye_adedi = models.PositiveIntegerField(default=0, verbose_name="Hediye ile verilen")
    tarih = models.DateTimeField(default=timezone.now, verbose_name="Tarih")
    kasiyer = models.CharField(max_length=150, blank=True, verbose_name="Kasiyer")

    @property
    def ara_toplam(self):
        """Indirim uygulanmadan onceki tutar."""
        return self.toplam + self.indirim_tutari

    class Meta:
        ordering = ("-tarih",)
        verbose_name = "Kahve Satışı"
        verbose_name_plural = "Kahve Satışları"
        indexes = [models.Index(fields=["-tarih"])]

    def __str__(self):
        kim = self.musteri.ad_soyad if self.musteri_id else "Kartsız"
        return f"{kim} - {self.toplam} TL"


class HediyeKahve(models.Model):
    class Durum(models.TextChoices):
        BEKLIYOR = "bekliyor", "Kullanılmayı bekliyor"
        KULLANILDI = "kullanildi", "Kullanıldı"

    musteri = models.ForeignKey(
        KahveMusteri, on_delete=models.CASCADE, related_name="hediyeler", verbose_name="Müşteri"
    )
    durum = models.CharField(max_length=16, choices=Durum.choices, default=Durum.BEKLIYOR, verbose_name="Durum")
    kazanma_tarihi = models.DateTimeField(default=timezone.now, verbose_name="Kazanma tarihi")
    kullanma_tarihi = models.DateTimeField(null=True, blank=True, verbose_name="Kullanma tarihi")
    kullanilan_icim = models.OneToOneField(
        KahveIcim, on_delete=models.SET_NULL, null=True, blank=True, related_name="hediye_kaydi"
    )

    class Meta:
        ordering = ("-kazanma_tarihi",)
        verbose_name = "Hediye Kahve"
        verbose_name_plural = "Hediye Kahveler"

    def __str__(self):
        return f"{self.musteri.ad_soyad} - {self.get_durum_display()}"


# ---------------------------------------------------------------------------
# Gorsel temizligi
# Sunucuda oksuz dosya birikmesin: gorsel degisince eskisi, urun silinince
# kendi dosyasi diskten de silinir. Sinyal kullaniyoruz cunku admin'deki toplu
# silme queryset.delete() cagirir ve model delete() metodunu atlar.
# ---------------------------------------------------------------------------


@receiver(pre_save, sender=Kahve)
def eski_gorseli_sil(sender, instance, **kwargs):
    """Gorsel degistirildiginde ya da temizlendiginde eskisini diskten sil."""
    if not instance.pk:
        return
    try:
        eski = Kahve.objects.get(pk=instance.pk).gorsel
    except Kahve.DoesNotExist:
        return
    if eski and eski.name != instance.gorsel.name:
        eski.delete(save=False)


@receiver(post_delete, sender=Kahve)
def urunle_birlikte_gorseli_sil(sender, instance, **kwargs):
    """Urun silinince gorseli de diskten sil."""
    if instance.gorsel:
        instance.gorsel.delete(save=False)
