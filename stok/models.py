from django.db import models
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
    Cep_Telefonu = models.PositiveBigIntegerField()
    borc = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    aciklama = models.TextField(null=True,blank=True)
    Ekleme_Tarih = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.isim_soyisim



class BorcHareketi(models.Model):
    musteri = models.ForeignKey(Musteri, on_delete=models.CASCADE)
    tutar = models.DecimalField(max_digits=10, decimal_places=2)
    tarih = models.DateTimeField(auto_now_add=True)
    aciklama = models.CharField(max_length=255)
    onceki_borc = models.DecimalField(max_digits=10, decimal_places=2)