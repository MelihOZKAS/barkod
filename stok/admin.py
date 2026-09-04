import csv
import math
from datetime import datetime
from decimal import Decimal

from django import forms
from django.apps import apps
from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.db import models, transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.html import format_html

from .disa_aktarma import hazir_sorgu, urunleri_yaz
from .etiket import EN_COK_URUN, OTURUM_ANAHTARI




# Register your models here.

from .models import (UrunGruplari, SepetUrun, Stok, Liste_Grup, Musteri,
                     BorcHareketi, Satis, SatisSatiri, StokHareketi)

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
    list_display = ("Urun_Adi","Barkod","Tutar","birim","fiyat_tarihi","stok_adedi",
                    "Favori","Stok_Durumu","Ekleme_Tarih","guncelleme_tarihi","etiket_baglantisi",)
    list_filter = ("Grup","Stok_Durumu",)
    list_editable = ("Favori","Tutar","birim","stok_adedi",)
    search_fields = ("Urun_Adi","Barkod",)

    formfield_overrides = {
        models.CharField: {'widget': forms.TextInput(attrs={'size':'90'})},
    }

    # Ustteki override butun CharField'leri 90 karakter genisliginde yapiyor.
    # "birim" liste icinde duzenlenebilir oldugu icin her satira 90 karakterlik
    # bir kutu dusuyor, tablo ekrana sigmaz hale geliyordu.
    KISA_ALANLAR = {"birim": 6, "uretim_yeri": 24}

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        genislik = self.KISA_ALANLAR.get(db_field.name)
        if genislik:
            kwargs["widget"] = forms.TextInput(attrs={"size": str(genislik)})
        return super().formfield_for_dbfield(db_field, request, **kwargs)




    actions = ["etiket_yazdir","csv_indir","Yuzde10ZamYap","Yuzde15ZamYap","Yuzde20ZamYap","Yuzde25ZamYap","Yuzde30ZamYap","Yuzde35ZamYap"]

    @admin.display(description="Etiket")
    def etiket_baglantisi(self, urun):
        """Tek urunun etiketini yeni sekmede acip DOGRUDAN yazdirir.

        Fiyat degisince tek etiket yeniden basmak icin listeden cikmaya gerek
        kalmasin; kasadaki kisi sayfayla ugrasmasin diye "bas=1" ile yazdirma
        penceresi kendiliginden aciliyor."""
        adres = f"{reverse('etiket')}?ids={urun.pk}&bas=1"
        return format_html('<a href="{}" target="_blank" rel="noopener">yazdır</a>', adres)

    @admin.action(description="Seçili ürünler için raf etiketi yazdır")
    def etiket_yazdir(self, request, queryset):
        """Secimi oturuma yazip etiket sayfasina gonderir.

        Id'ler URL'e degil oturuma konuyor: "Tumunu sec" ile yuzlerce urun
        secildiginde adres satiri tasmasin, sayfa yenilenince secim durmaya
        devam etsin.
        """
        idler = list(queryset.values_list("id", flat=True))
        if not idler:
            self.message_user(request, "Etiket basılacak ürün seçilmedi.", messages.WARNING)
            return None
        if len(idler) > EN_COK_URUN:
            self.message_user(
                request,
                f"{len(idler)} ürün seçildi; ilk {EN_COK_URUN} tanesinin etiketi basılacak.",
                messages.WARNING,
            )
            idler = idler[:EN_COK_URUN]
        request.session[OTURUM_ANAHTARI] = idler
        return redirect("etiket")

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




class MukerrerMusteriFiltresi(admin.SimpleListFilter):
    """Ayni isimden birden fazla kayit varsa hepsini yan yana getirir.

    Kasadaki hizli ekleme bir donem ayni musteriyi ikinci kez kaydediyordu;
    borcu olan hane ile bos hane listede yan yana duruyor, kasiyer yanlis
    olani seciyordu. Bu filtre onlari bulmak icin.
    """

    title = "Mükerrer kayıt"
    parameter_name = "mukerrer"

    def lookups(self, request, model_admin):
        return (("evet", "Aynı isimden birden fazla"),)

    def queryset(self, request, queryset):
        if self.value() != "evet":
            return queryset
        tekrarlayan = (
            Musteri.objects.values("isim_soyisim")
            .annotate(adet=models.Count("id"))
            .filter(adet__gt=1)
            .values_list("isim_soyisim", flat=True)
        )
        return queryset.filter(isim_soyisim__in=list(tekrarlayan))


class MusteriAdmin(admin.ModelAdmin):
    list_display = ("isim_soyisim", "Cep_Telefonu", "borc", "Ekleme_Tarih", "id")
    search_fields = ("isim_soyisim","Cep_Telefonu",)
    list_filter = (MukerrerMusteriFiltresi, "Ekleme_Tarih")
    ordering = ("isim_soyisim", "Ekleme_Tarih")
    actions = ["musterileri_birlestir"]

    @admin.action(description="Seçili müşterileri tek kayıtta birleştir")
    def musterileri_birlestir(self, request, queryset):
        """Mukerrer musteri kayitlarini tek haneye toplar.

        Iki asamali: once ne olacagini gosteren onay sayfasi cikar, kullanici
        onaylamadan hicbir sey degismez. Canli veri; yanlis secimle iki ayri
        musterinin borcu birlesirse geri almak zor.
        """
        secilenler = list(queryset.order_by("Ekleme_Tarih", "id"))
        if len(secilenler) < 2:
            self.message_user(
                request, "Birleştirmek için en az iki müşteri seçin.", messages.WARNING
            )
            return None

        hedef, digerleri = secilenler[0], secilenler[1:]
        # Cross-app import: kahve zaten stok'u iceriye aliyor, ters yonde
        # dogrudan import dairesel bagimlilik yapardi.
        KahveSatis = apps.get_model("kahve", "KahveSatis")

        if request.POST.get("birlestir_onay") != "evet":
            return TemplateResponse(request, "admin/stok/musteri/birlestir_onay.html", {
                **self.admin_site.each_context(request),
                "baslik": "Müşterileri birleştir",
                "hedef": hedef,
                "digerleri": digerleri,
                "toplam_borc": sum((m.borc for m in secilenler), Decimal("0.00")),
                "hareket_sayisi": BorcHareketi.objects.filter(musteri__in=secilenler).count(),
                "secilenler": secilenler,
                "eylem": "musterileri_birlestir",
                "secim_alani": ACTION_CHECKBOX_NAME,
            })

        with transaction.atomic():
            BorcHareketi.objects.filter(musteri__in=digerleri).update(musteri=hedef)
            Satis.objects.filter(borc_musteri__in=digerleri).update(borc_musteri=hedef)
            KahveSatis.objects.filter(borc_musteri__in=digerleri).update(borc_musteri=hedef)

            hedef.borc = sum((m.borc for m in secilenler), Decimal("0.00"))
            if not hedef.Cep_Telefonu:
                for m in digerleri:
                    if m.Cep_Telefonu:
                        hedef.Cep_Telefonu = m.Cep_Telefonu
                        break
            not_satiri = "%s: %d mükerrer kayıt bu haneyle birleştirildi." % (
                datetime.now().strftime("%d.%m.%Y"), len(digerleri),
            )
            hedef.aciklama = ((hedef.aciklama or "").strip() + "\n" + not_satiri).strip()
            hedef.save()

            Musteri.objects.filter(pk__in=[m.pk for m in digerleri]).delete()

        self.message_user(
            request,
            "%s: %d kayıt birleştirildi, borç %s ₺ oldu."
            % (hedef.isim_soyisim, len(secilenler), hedef.borc),
            messages.SUCCESS,
        )
        return None


admin.site.register(Musteri, MusteriAdmin)


class SatisSatiriSatiri(admin.TabularInline):
    model = SatisSatiri
    extra = 0
    readonly_fields = ("urun", "urun_adi", "birim_fiyat", "miktar")
    can_delete = False


@admin.register(Satis)
class SatisAdmin(admin.ModelAdmin):
    list_display = ("tarih", "toplam", "odeme_turu", "nakit_tutar", "kart_tutar",
                    "borc_tutar", "borc_musteri", "kalem_adedi", "kasiyer")
    list_filter = ("odeme_turu", "tarih")
    search_fields = ("borc_musteri__isim_soyisim", "kasiyer")
    date_hierarchy = "tarih"
    inlines = [SatisSatiriSatiri]
    readonly_fields = ("tarih",)


@admin.register(StokHareketi)
class StokHareketiAdmin(admin.ModelAdmin):
    list_display = ("tarih", "urun", "tur", "miktar", "onceki_adet", "sonraki_adet",
                    "aciklama", "kullanici")
    list_filter = ("tur", "tarih")
    search_fields = ("urun__Urun_Adi", "urun__Barkod")
    date_hierarchy = "tarih"


@admin.register(BorcHareketi)
class BorcHareketiAdmin(admin.ModelAdmin):
    list_display = ("tarih", "musteri", "tutar", "onceki_borc", "kisa_aciklama")
    list_filter = ("tarih",)
    search_fields = ("musteri__isim_soyisim", "aciklama")
    date_hierarchy = "tarih"

    @admin.display(description="Açıklama")
    def kisa_aciklama(self, nesne):
        metin = (nesne.aciklama or "").replace("\n", " · ")
        return metin[:90] + ("…" if len(metin) > 90 else "")
