from django.contrib import admin
from django import forms
from django.db import models


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


admin.site.register(Stok, StokAdmin)




class MusteriAdmin(admin.ModelAdmin):
    list_display = ("isim_soyisim","Cep_Telefonu",)

admin.site.register(Musteri, MusteriAdmin)