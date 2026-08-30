from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal


# Create your models here.


class UrunGruplari(models.Model):
    Grup_Adi = models.CharField(max_length=255, unique=True)
    def __str__(self):
        return f"{self.Grup_Adi}"

    class Meta:
        verbose_name_plural = 'Urun Grupları'

class Liste_Grup(models.Model):
    Grup_Adi = models.CharField(max_length=255, unique=True)
    def __str__(self):
        return f"{self.Grup_Adi}"

    class Meta:
        verbose_name_plural = 'Liste Favori Grupları'
class Stok(models.Model):
    Urun_Adi = models.CharField(max_length=255)
    Barkod = models.PositiveBigIntegerField(unique=True)
    Urun_Genel = models.CharField(max_length=500, editable=False,blank=True, null=True)
    Grup = models.ManyToManyField(UrunGruplari, blank=True)
    Liste_grup = models.ForeignKey(Liste_Grup,null=True, blank=True,on_delete=models.SET_NULL)
    Tutar = models.DecimalField(max_digits=44, decimal_places=2,blank=True, null=True, default=Decimal('0.00'))
    Favori = models.BooleanField(default=False)
    Stok_Durumu = models.BooleanField(default=True)
    # BOS BIRAKILIRSA stok takibi yapilmaz. Binlerce urunun sayimi bir gunde
    # yapilamaz; sadece takip etmek istedigin urune adet gir, digerleri
    # eskisi gibi calismaya devam etsin.
    stok_adedi = models.IntegerField(
        null=True, blank=True,
        verbose_name="Stok adedi",
        help_text="Boş bırakılırsa bu ürün için stok takibi yapılmaz.",
    )
    Oto_Sil = models.BooleanField(default=False)
    Ekleme_Tarih = models.DateTimeField(auto_now_add=True)
    guncelleme_tarihi = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.Urun_Adi}"
    class Meta:
        verbose_name_plural = 'Stok urunleri'
    def save(self, *args, **kwargs):
        self.Urun_Genel = f"{self.Urun_Adi} - {self.Barkod}"
        super().save(*args, **kwargs)



from django.db import models
from django.contrib.auth.models import User

class SepetUrun(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    urun = models.ForeignKey(Stok, on_delete=models.CASCADE)
    miktar = models.PositiveIntegerField(default=1)


    def __str__(self):
        return f"{self.urun.Urun_Adi} ({self.miktar})"




class Musteri(models.Model):
    isim_soyisim = models.CharField(max_length=255)
    Cep_Telefonu = models.PositiveBigIntegerField(null=True,blank=True)
    borc = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    aciklama = models.TextField(null=True,blank=True)
    Ekleme_Tarih = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.isim_soyisim



class BorcHareketi(models.Model):
    musteri = models.ForeignKey(Musteri, on_delete=models.CASCADE)
    tutar = models.DecimalField(max_digits=10, decimal_places=2)
    tarih = models.DateTimeField(auto_now_add=True)
    # Alinan urunler de aciklamaya yaziliyor; 255 karakter yetmiyor.
    aciklama = models.TextField()
    onceki_borc = models.DecimalField(max_digits=10, decimal_places=2)


class StokHareketi(models.Model):
    """Bir urunun adedini degistiren her olay.

    Satis, mal girisi, sayim duzeltmesi ve iade ayni tabloda; "bu urun neden
    3'e dustu" sorusunun cevabi burada duruyor.
    """

    class Tur(models.TextChoices):
        SATIS = "satis", "Satış"
        GIRIS = "giris", "Mal girişi"
        DUZELTME = "duzeltme", "Sayım düzeltmesi"
        IADE = "iade", "İade"

    urun = models.ForeignKey(Stok, on_delete=models.CASCADE, related_name="hareketler",
                             verbose_name="Ürün")
    tur = models.CharField(max_length=16, choices=Tur.choices, verbose_name="Hareket türü")
    # Satista eksi, giriste arti. Isaretiyle birlikte saklanir.
    miktar = models.IntegerField(verbose_name="Miktar")
    onceki_adet = models.IntegerField(null=True, blank=True, verbose_name="Önceki adet")
    sonraki_adet = models.IntegerField(null=True, blank=True, verbose_name="Sonraki adet")
    aciklama = models.CharField(max_length=255, blank=True, verbose_name="Açıklama")
    kullanici = models.CharField(max_length=150, blank=True, verbose_name="Kullanıcı")
    tarih = models.DateTimeField(default=timezone.now, verbose_name="Tarih")

    class Meta:
        ordering = ("-tarih",)
        verbose_name = "Stok hareketi"
        verbose_name_plural = "Stok hareketleri"

    def __str__(self):
        return f"{self.urun.Urun_Adi} {self.miktar:+d} ({self.get_tur_display()})"


class Satis(models.Model):
    """Kirtasiye tezgahinda tamamlanan satis.

    Onceden sepet sadece siliniyordu; ne kadar nakit ne kadar kart girdigi
    hicbir yerde yazmiyordu. Kasa raporu bu tabloya dayaniyor.
    """

    class Odeme(models.TextChoices):
        NAKIT = "nakit", "Nakit"
        KART = "kart", "Kredi kartı"
        PARCALI = "parcali", "Parçalı"
        BORC = "borc", "Borca yazıldı"

    toplam = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Toplam")
    nakit_tutar = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Nakit")
    kart_tutar = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Kredi kartı")
    # Borca yazilan kisim. Parcali aktarmada tutarin bir kismi nakit alinip
    # kalani borca yazilabiliyor; o yuzden ayri alan.
    borc_tutar = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Borca yazılan")
    odeme_turu = models.CharField(max_length=16, choices=Odeme.choices,
                                  default=Odeme.NAKIT, verbose_name="Ödeme türü")
    borc_musteri = models.ForeignKey(
        Musteri, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="kirtasiye_satislari", verbose_name="Borç yazılan müşteri",
    )
    kalem_adedi = models.PositiveIntegerField(default=0, verbose_name="Kalem adedi")
    kasiyer = models.CharField(max_length=150, blank=True, verbose_name="Kasiyer")
    notlar = models.TextField(blank=True, verbose_name="Not")
    tarih = models.DateTimeField(default=timezone.now, verbose_name="Tarih")

    class Meta:
        ordering = ("-tarih",)
        verbose_name = "Kırtasiye satışı"
        verbose_name_plural = "Kırtasiye satışları"

    def __str__(self):
        return f"{self.toplam} ₺ — {self.get_odeme_turu_display()}"


class SatisSatiri(models.Model):
    """Satistaki tek bir urun. Fiyat o anki fiyattir, sonra degisse de kayit bozulmaz."""

    satis = models.ForeignKey(Satis, on_delete=models.CASCADE, related_name="satirlar")
    urun = models.ForeignKey(Stok, on_delete=models.SET_NULL, null=True, verbose_name="Ürün")
    urun_adi = models.CharField(max_length=255, verbose_name="Ürün adı")
    birim_fiyat = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Birim fiyat")
    miktar = models.PositiveIntegerField(default=1, verbose_name="Miktar")

    class Meta:
        verbose_name = "Satış satırı"
        verbose_name_plural = "Satış satırları"

    @property
    def ara_toplam(self):
        return self.birim_fiyat * self.miktar

    def __str__(self):
        return f"{self.miktar}x {self.urun_adi}"
