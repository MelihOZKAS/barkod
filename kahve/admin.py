from django.contrib import admin, messages
from django.urls import reverse
from django.utils.html import format_html

from . import sadakat
from .models import (
    HediyeKahve, Kahve, KahveAyar, KahveIcim, KahveKategori, KahveMusteri, KahveSatis,
)


@admin.register(KahveAyar)
class KahveAyarAdmin(admin.ModelAdmin):
    fieldsets = (
        ("İşletme", {"fields": ("isletme_adi", "slogan")}),
        (
            "Sadakat kuralları",
            {
                "fields": ("hediye_icin_kahve", "gecerlilik_gun"),
                "description": "Örnek: 5 kahve / 30 gün → 30 gün içinde 5 kahve içen 6. kahveyi "
                "hediye alır. 30 günü dolan kahve sayaçtan düşer.",
            },
        ),
        (
            "Firebase (mobil uygulama girişi)",
            {
                "fields": (
                    "firebase_api_key",
                    "firebase_auth_domain",
                    "firebase_project_id",
                    "firebase_app_id",
                    "firebase_sender_id",
                    "firebase_storage_bucket",
                ),
                "description": "Firebase konsolu → Proje ayarları → Web uygulaması "
                "bilgilerini buraya yapıştırın. <b>Sadece mobil uygulama kullanır</b> — "
                "web sitesinde müşteri girişi yoktur.",
            },
        ),
        ("Anahtarlar", {"fields": ("cron_anahtari", "mobil_api_anahtari", "cron_adresi")}),
    )
    readonly_fields = ("cron_adresi",)

    def has_add_permission(self, request):
        return not KahveAyar.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="Günlük cron adresi")
    def cron_adresi(self, obj):
        if not obj or not obj.pk:
            return "-"
        adres = f"/kahve/cron/gunluk-temizlik/?anahtar={obj.cron_anahtari}"
        return format_html(
            '<code style="user-select:all">{}</code><br>'
            "<small>PHP sitenizdeki cron her gece 02:00'de bu adrese GET isteği atsın. "
            "Mobil uygulama ise her istekte <code>X-Kahve-Key: {}</code> başlığını gönderir.</small>",
            adres,
            obj.mobil_api_anahtari,
        )


@admin.register(KahveKategori)
class KahveKategoriAdmin(admin.ModelAdmin):
    list_display = ("ad", "urun_sayisi", "sira", "aktif")
    list_editable = ("sira", "aktif")
    search_fields = ("ad",)

    @admin.display(description="Ürün sayısı")
    def urun_sayisi(self, obj):
        return obj.urunler.count()


@admin.register(Kahve)
class KahveAdmin(admin.ModelAdmin):
    list_display = ("onizleme", "ad", "kategori", "fiyat", "aktif", "damga_veriyor", "hediye_gecerli", "sira")
    list_display_links = ("onizleme", "ad")
    list_editable = ("kategori", "fiyat", "aktif", "damga_veriyor", "hediye_gecerli", "sira")
    search_fields = ("ad", "aciklama", "icindekiler")
    list_filter = ("kategori", "aktif", "damga_veriyor", "hediye_gecerli")
    save_on_top = True

    fieldsets = (
        ("Ürün", {"fields": ("ad", "kategori", "fiyat")}),
        (
            "Görsel",
            {
                "fields": ("gorsel", "onizleme"),
                "description": "Kare veya yatay (16:9) bir fotoğraf en iyi sonucu verir. "
                "Görsel eklemezseniz menüde kahve halkası deseni görünür.",
            },
        ),
        (
            "Detay",
            {
                "fields": ("aciklama", "icindekiler"),
                "description": "Açıklama menüde kahve adının altında görünür. "
                "İçindekilerdeki her satır ayrı bir etiket olur.",
            },
        ),
        (
            "Menüde görünüm",
            {"fields": ("sira", "aktif")},
        ),
        (
            "Sadakat",
            {
                "fields": ("damga_veriyor", "hediye_gecerli"),
                "description": "Kahveler için <b>Hediye sayacına +1</b> açık olmalı. "
                "Kurabiye, su gibi ürünlerde kapalı bırakın — satılsa bile damga kazandırmaz.",
            },
        ),
    )
    readonly_fields = ("onizleme",)

    @admin.display(description="Önizleme")
    def onizleme(self, obj):
        if obj.gorsel:
            return format_html(
                '<img src="{}" style="width:110px;height:110px;object-fit:cover;'
                'border-radius:10px;border:1px solid #ddd">',
                obj.gorsel.url,
            )
        return format_html('<span style="color:#999">görsel yok</span>')


class KahveIcimInline(admin.TabularInline):
    model = KahveIcim
    extra = 0
    fields = ("kahve_adi", "durum", "tarih", "son_gecerlilik", "ekleyen")
    readonly_fields = ("kahve_adi", "tarih", "son_gecerlilik", "ekleyen")
    ordering = ("-tarih",)
    verbose_name = "Kahve içimi"
    verbose_name_plural = "Kahve içimleri"


@admin.register(KahveMusteri)
class KahveMusteriAdmin(admin.ModelAdmin):
    list_display = ("ad_soyad", "kod", "telefon", "sayac", "hediye", "toplam", "kayit_tarihi", "aktif")
    list_filter = ("aktif", "kayit_tarihi")
    search_fields = ("ad_soyad", "kod", "email", "telefon", "firebase_uid")
    readonly_fields = ("kod", "qr_token", "kart_baglantisi", "kayit_tarihi", "son_gorulme")

    fieldsets = (
        ("Müşteri", {"fields": ("ad_soyad", "telefon", "email", "aktif")}),
        (
            "Kart",
            {
                "fields": ("kod", "qr_token", "kart_baglantisi"),
                "description": "Barkod ve QR müşteri oluşturulurken otomatik üretilir, değiştirilemez.",
            },
        ),
        ("Kayıt", {"fields": ("firebase_uid", "kayit_tarihi", "son_gorulme")}),
    )
    inlines = (KahveIcimInline,)
    actions = ("kahve_yaz", "hediye_ver", "sayaci_sifirla")

    @admin.display(description="Sayaçta")
    def sayac(self, obj):
        return obj.aktif_kahve_sayisi

    @admin.display(description="Bekleyen hediye")
    def hediye(self, obj):
        return obj.bekleyen_hediye_sayisi

    @admin.display(description="Toplam kahve")
    def toplam(self, obj):
        return obj.toplam_icim_sayisi

    @admin.display(description="Barkod / QR kartı")
    def kart_baglantisi(self, obj):
        if not obj.pk:
            return "-"
        adres = reverse("kahve:kart-qr", args=[obj.qr_token])
        return format_html(
            '<a href="{}" target="_blank">Kartı aç</a> &nbsp;|&nbsp; '
            'barkod: <code style="user-select:all">{}</code>',
            adres,
            obj.kod,
        )

    @admin.action(description="Seçili müşterilere 1 kahve yaz")
    def kahve_yaz(self, request, queryset):
        kazanan = 0
        for musteri in queryset:
            sonuc = sadakat.kahve_ekle(musteri, ekleyen=request.user.get_username())
            kazanan += len(sonuc["kazanilan_hediyeler"])
        self.message_user(
            request, f"{queryset.count()} müşteriye kahve yazıldı. {kazanan} hediye kazanıldı."
        )

    @admin.action(description="Seçili müşterilere 1 hediye kahve tanımla")
    def hediye_ver(self, request, queryset):
        for musteri in queryset:
            HediyeKahve.objects.create(musteri=musteri)
        self.message_user(request, f"{queryset.count()} müşteriye hediye kahve tanımlandı.")

    @admin.action(description="Sayacı sıfırla (bekleyen kahveleri düşür)")
    def sayaci_sifirla(self, request, queryset):
        toplam = 0
        for musteri in queryset:
            toplam += musteri.aktif_icimler().update(durum=KahveIcim.Durum.DOLDU)
        self.message_user(request, f"{toplam} kahve sayaçtan düşürüldü.", messages.WARNING)


class SatisIcimInline(admin.TabularInline):
    model = KahveIcim
    extra = 0
    fields = ("kahve_adi", "fiyat", "durum")
    readonly_fields = ("kahve_adi", "fiyat", "durum")
    can_delete = False
    verbose_name = "Fincan"
    verbose_name_plural = "Satıştaki fincanlar"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(KahveSatis)
class KahveSatisAdmin(admin.ModelAdmin):
    list_display = ("tarih", "musteri_adi", "fincan_adedi", "hediye_adedi", "toplam", "odeme", "kasiyer")
    list_filter = ("odeme_turu", "tarih")
    search_fields = ("musteri__ad_soyad", "musteri__kod", "kasiyer")
    date_hierarchy = "tarih"
    autocomplete_fields = ("musteri",)
    inlines = (SatisIcimInline,)
    readonly_fields = ("tarih",)

    @admin.display(description="Müşteri")
    def musteri_adi(self, obj):
        return obj.musteri.ad_soyad if obj.musteri_id else "Kartsız"

    @admin.display(description="Ödeme")
    def odeme(self, obj):
        if obj.odeme_turu == KahveSatis.Odeme.PARCALI:
            return f"Parçalı ({obj.nakit_tutar:.0f} nakit / {obj.kart_tutar:.0f} kart)"
        return obj.get_odeme_turu_display()


@admin.register(KahveIcim)
class KahveIcimAdmin(admin.ModelAdmin):
    list_display = ("musteri", "kahve_adi", "fiyat", "durum", "tarih", "son_gecerlilik", "kalan", "ekleyen")
    list_filter = ("durum", "tarih", "kahve")
    autocomplete_fields = ("musteri", "kahve")
    search_fields = ("musteri__ad_soyad", "musteri__kod", "kahve_adi")
    date_hierarchy = "tarih"

    @admin.display(description="Kalan gün")
    def kalan(self, obj):
        gun = obj.kalan_gun
        return "-" if gun is None else f"{gun} gün"


@admin.register(HediyeKahve)
class HediyeKahveAdmin(admin.ModelAdmin):
    list_display = ("musteri", "durum", "kazanma_tarihi", "kullanma_tarihi")
    list_filter = ("durum", "kazanma_tarihi")
    search_fields = ("musteri__ad_soyad", "musteri__kod")
    autocomplete_fields = ("musteri",)
