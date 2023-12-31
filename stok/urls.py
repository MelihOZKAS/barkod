from django.urls import path
from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("urun-ara/", views.urun_ara, name='Arama'),
    path("urun-ara-yeni/", views.urun_ara_yeni, name='AramaYeni'),
    path("urun-ara-yeni-2/", views.urun_ara_yeni_iki, name='AramaYeni2'),
    path("urun-ara-beyaz/", views.urun_ara_beyaz, name='urun-ara-beyaz'),
    path("logout/", views.logout, name='cikis-yap'),
    path("panel/", views.konsol_home_detail, name='panel'),
    path("manuel-tutar/", views.manuel_tutar_ekle, name='manuel-tutar'),
    path("manuel-tutar-beyaz/", views.manuel_tutar_ekle_beyaz, name='manuel-tutar-beyaz'),
    path("sepeti-sifirla/", views.sepeti_sifirla, name='sepeti-sifirla'),
    path("sepeti-sifirla-beyaz/", views.sepeti_sifirla_beyaz, name='sepeti-sifirla-beyaz'),
    path("musteri-listesi/", views.Bayi_Listesi, name='musteri-listesi'),
    path("musteri-ekle/", views.musteri_ekle, name='musteri-ekle'),

    path("sepete-git/", views.musteri_ekle, name='sepete-git'),
    path("fazlalik-sil/", views.stok_sil, name='stok_sil'),
    path("oto-ekle/", views.topluekle, name='oto-ekle'),
    path("oto-grupla/", views.barkodlari_gruba_ekle, name='oto-grupla'),


    path("bakiye/<int:musteri_id>/", views.bakiye, name='bakiye'),
    path("borc-duzenle/<int:musteri_id>/", views.borc_duzenle, name='borc-duzenle'),
    path("bakiye-hareketi/<int:musteri_id>/", views.bakiyeHareketi, name='bakiye-hareketi'),
    path("urun_miktar_guncelle/<int:urun_id>/", views.urun_miktar_guncelle, name='urun_miktar_guncelle'),


    path('sepete-ekle/', views.sepete_ekle, name='sepete-ekle'),
    path('sepete-ekle-beyaz/', views.sepete_ekle_beyaz, name='sepete-ekle-beyaz'),
    path('sepet/urun-sil/<int:urun_id>/', views.sepet_urun_sil, name='sepet_urun_sil'),
    path('sepet/urun-sil-beyaz/<int:urun_id>/', views.sepet_urun_sil_beyaz, name='sepet_urun_sil-beyaz'),

]
