from django.contrib import admin
from django import forms
from django.db import models
import math



# Register your models here.

from .models import UrunGruplari,SepetUrun,Stok,Liste_Grup,Musteri

class GruplarAdmin(admin.ModelAdmin):
    list_display = ("Grup_Adi",)

admin.site.register(UrunGruplari, GruplarAdmin)
class ListFavoriAdmin(admin.ModelAdmin):
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




    actions = ["Yuzde10ZamYap","Yuzde15ZamYap","Yuzde20ZamYap","Yuzde25ZamYap","Yuzde30ZamYap","Yuzde35ZamYap"]


    def Yuzde10ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * 1.10) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde10ZamYap.short_description = "Seçili ürünlere Yuzde:10 zam uygula"
    def Yuzde15ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * 1.15) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
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
            obj.Tutar = math.floor(obj.Tutar * 1.20) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde20ZamYap.short_description = "Seçili ürünlere Yuzde:20 zam uygula"
    def Yuzde25ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * 1.25) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde25ZamYap.short_description = "Seçili ürünlere Yuzde:25 zam uygula"

    def Yuzde30ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * 1.30) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde30ZamYap.short_description = "Seçili ürünlere Yuzde:30 zam uygula"

    def Yuzde35ZamYap(self, request, queryset):
        for obj in queryset:
            obj.Tutar = math.floor(obj.Tutar * 1.35) + 1  # %25 zam uygula, küsüratı sil ve 1 ekle
            obj.save()

    Yuzde30ZamYap.short_description = "Seçili ürünlere Yuzde:35 zam uygula"

admin.site.register(Stok, StokAdmin)




class MusteriAdmin(admin.ModelAdmin):
    list_display = ("isim_soyisim","Cep_Telefonu",)

admin.site.register(Musteri, MusteriAdmin)