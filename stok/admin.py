import csv
import math
from datetime import datetime
from decimal import Decimal

from django import forms
from django.contrib import admin
from django.db import models
from django.http import HttpResponse

from .disa_aktarma import hazir_sorgu, urunleri_yaz




# Register your models here.

from .models import UrunGruplari,SepetUrun,Stok,Liste_Grup,Musteri

class GrupCsvKarisimi:
    """Grup tablolari icin ortak CSV indirme eylemi."""

    actions = ["csv_indir"]

    @admin.action(description="Seçili grupları CSV olarak indir (yedek)")
    def csv_indir(self, request, queryset):
        cevap = HttpResponse(content_type="text/csv; charset=utf-8")
        ad = self.model._meta.model_name
        cevap["Content-Disposition"] = (
            f'attachment; filename="{ad}-yedek-{datetime.now():%Y%m%d-%H%M}.csv"'
        )
        cevap.write("\ufeff")
        yazici = csv.writer(cevap)
        yazici.writerow(["grup_adi"])
        for grup in queryset.order_by("Grup_Adi"):
            yazici.writerow([grup.Grup_Adi])
        return cevap


class GruplarAdmin(GrupCsvKarisimi, admin.ModelAdmin):
    list_display = ("Grup_Adi",)

admin.site.register(UrunGruplari, GruplarAdmin)
class ListFavoriAdmin(GrupCsvKarisimi, admin.ModelAdmin):
    list_display = ("Grup_Adi",)

admin.site.register(Liste_Grup, ListFavoriAdmin)



class StokAdmin(admin.ModelAdmin):
    list_display = ("Urun_Adi","Barkod","Tutar","Favori","Stok_Durumu","Ekleme_Tarih","guncelleme_tarihi",)
    list_filter = ("Grup","Stok_Durumu",)
    list_editable = ("Favori","Tutar",)
    search_fields = ("Urun_Adi","Barkod",)

    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size':'90'})},
    }




    actions = ["csv_indir","Yuzde10ZamYap","Yuzde15ZamYap","Yuzde20ZamYap","Yuzde25ZamYap","Yuzde30ZamYap","Yuzde35ZamYap"]

    @admin.action(description="Seçili ürünleri CSV olarak indir (yedek)")
    def csv_indir(self, request, queryset):
        """Indirilen dosya stok_ice_aktar ile geri yuklenebilir.

        Tum katalogu almak icin ustteki kutuyu isaretleyip cikan
        "Tumunu sec" baglantisina tiklayin.
        """
        cevap = HttpResponse(content_type="text/csv; charset=utf-8")
        dosya_adi = f"stok-yedek-{datetime.now():%Y%m%d-%H%M}.csv"
        cevap["Content-Disposition"] = f'attachment; filename="{dosya_adi}"'
        cevap.write("\ufeff")  # Excel icin tek BOM; charset utf-8 olmali yoksa her satira eklenir
        urunleri_yaz(cevap, hazir_sorgu(queryset.order_by("Urun_Adi")))
        return cevap


    def Yuzde10ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * Decimal("1.10")) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde10ZamYap.short_description = "Seçili ürünlere Yuzde:10 zam uygula"
    def Yuzde15ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * Decimal("1.15")) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde15ZamYap.short_description = "Seçili ürünlere Yuzde:15 zam uygula"
    #def Yuzde15ZamYap(self, request, queryset):
    #    for obj in queryset:
    #        obj.Tutar = math.floor(obj.Tutar * 1.15) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
    #        obj.save()
#
    #Yuzde15ZamYap.short_description = "Seçili ürünlere Yuzde:15 zam uygula"

    def Yuzde20ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * Decimal("1.20")) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde20ZamYap.short_description = "Seçili ürünlere Yuzde:20 zam uygula"
    def Yuzde25ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * Decimal("1.25")) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde25ZamYap.short_description = "Seçili ürünlere Yuzde:25 zam uygula"

    def Yuzde30ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * Decimal("1.30")) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde30ZamYap.short_description = "Seçili ürünlere Yuzde:30 zam uygula"

    def Yuzde35ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * Decimal("1.35")) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde30ZamYap.short_description = "Seçili ürünlere Yuzde:35 zam uygula"

admin.site.register(Stok, StokAdmin)




class MusteriAdmin(admin.ModelAdmin):
    list_display = ("isim_soyisim","Cep_Telefonu","borc",)
    search_fields = ("isim_soyisim","Cep_Telefonu",)
    list_filter = ("Ekleme_Tarih",)

admin.site.register(Musteri, MusteriAdmin)