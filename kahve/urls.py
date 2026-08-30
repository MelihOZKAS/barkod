from django.urls import path

from . import views

app_name = "kahve"

urlpatterns = [
    # Halka acik
    path("", views.menu, name="menu"),

    # Personel: admin'den bir musterinin kartini acar
    path("k/<uuid:token>/", views.kart_qr, name="kart-qr"),

    # Kasa (personel)
    path("kasa/", views.kasa, name="kasa"),
    path("kasa/durum/", views.kasa_durum, name="kasa-durum"),
    path("kasa/sepete-ekle/", views.kasa_sepete_ekle, name="kasa-sepete-ekle"),
    path("kasa/adet/", views.kasa_adet_degistir, name="kasa-adet"),
    path("kasa/satir-sil/", views.kasa_satir_sil, name="kasa-satir-sil"),
    path("kasa/hediye/", views.kasa_hediye_degistir, name="kasa-hediye"),
    path("kasa/sifirla/", views.kasa_sepeti_temizle, name="kasa-sifirla"),
    path("kasa/musteri-bul/", views.kasa_musteri_bul, name="kasa-musteri-bul"),
    path("kasa/musteri-cikar/", views.kasa_musteri_cikar, name="kasa-musteri-cikar"),
    path("kasa/musteri-ekle/", views.kasa_musteri_ekle, name="kasa-musteri-ekle"),
    path("kasa/satis-tamamla/", views.kasa_satis_tamamla, name="kasa-satis-tamamla"),
    path("kasa/menu-yukle/", views.kasa_menu_yukle, name="kasa-menu-yukle"),

    # Gece cron'u
    path("cron/gunluk-temizlik/", views.cron_temizlik, name="cron-temizlik"),

    # Mobil API
    path("api/v1/ayarlar/", views.api_ayarlar, name="api-ayarlar"),
    path("api/v1/menu/", views.api_menu, name="api-menu"),
    path("api/v1/oturum/", views.api_oturum, name="api-oturum"),
    path("api/v1/kart/", views.api_kart, name="api-kart"),
    path("api/v1/gecmis/", views.api_gecmis, name="api-gecmis"),
]
