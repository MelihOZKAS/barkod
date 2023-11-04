from django.contrib import admin
from django import forms


# Register your models here.

from .models import UrunGruplari,SepetUrun,Stok,Liste_Grup,Musteri

class GruplarAdmin(admin.ModelAdmin):
    list_display = ("Grup_Adi",)

admin.site.register(UrunGruplari, GruplarAdmin)
class ListFavoriAdmin(admin.ModelAdmin):
    list_display = ("Grup_Adi",)

admin.site.register(Liste_Grup, ListFavoriAdmin)



class UrunAdiWidget(forms.TextInput):
    attrs = {'size': 90}
class StokAdmin(admin.ModelAdmin):
    list_display = ("Urun_Adi","Barkod","Tutar","Favori","Stok_Durumu","Ekleme_Tarih","guncelleme_tarihi",)
    list_filter = ("Grup","Stok_Durumu",)
    list_editable = ("Favori","Tutar",)
    search_fields = ("Urun_Adi","Barkod",)

    form = admin.forms.ModelForm(
        model=Stok,
        widgets={'Urun_Adi': UrunAdiWidget()},
    )

admin.site.register(Stok, StokAdmin)




class MusteriAdmin(admin.ModelAdmin):
    list_display = ("isim_soyisim","Cep_Telefonu",)

admin.site.register(Musteri, MusteriAdmin)