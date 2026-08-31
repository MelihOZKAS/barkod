"""Kahve modulu testleri.

Calistirmak icin:
    python manage.py test kahve
"""

import json
import os
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from PIL import Image

from stok.models import BorcHareketi, Musteri

from . import kasa as kasa_sepeti
from . import menu_verisi, sadakat
from .models import (
    HediyeKahve, Kahve, KahveAyar, KahveIcim, KahveKategori, KahveMusteri, KahveSatis,
)


class SadakatKuraliTesti(TestCase):
    """Isin kalbi: sayac, sure ve hediye kurallari."""

    def setUp(self):
        self.ayar = KahveAyar.al()
        self.ayar.hediye_icin_kahve = 5
        self.ayar.gecerlilik_gun = 7
        self.ayar.save()
        self.latte = Kahve.objects.create(ad="Latte", fiyat=90, damga_veriyor=True)
        self.musteri = KahveMusteri.objects.create(ad_soyad="Test Musteri")

    def test_suresi_dolan_kahve_sayactan_duser(self):
        """7 gun sinir, 4 kahve; 8 gun onceki kahvenin suresi dolunca sayac 3'e iner."""
        simdi = timezone.now()
        for gun_once in (8, 6, 4, 2):
            sadakat.kahve_ekle(self.musteri, self.latte, tarih=simdi - timedelta(days=gun_once))
        self.assertEqual(self.musteri.aktif_kahve_sayisi, 4)

        dusen = sadakat.suresi_dolanlari_dusur()

        self.assertEqual(dusen, 1)
        self.assertEqual(self.musteri.aktif_kahve_sayisi, 3)
        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 0)

    def test_suresi_dolan_kayit_silinmez_gecmiste_kalir(self):
        sadakat.kahve_ekle(self.musteri, self.latte, tarih=timezone.now() - timedelta(days=9))
        sadakat.suresi_dolanlari_dusur()

        kayit = self.musteri.icimler.get()
        self.assertEqual(kayit.durum, KahveIcim.Durum.DOLDU)
        self.assertEqual(self.musteri.icimler.count(), 1)

    def test_esige_gelince_hediye_kazanilir_ve_sayac_sifirlanir(self):
        for _ in range(4):
            sadakat.kahve_ekle(self.musteri, self.latte)
        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 0)

        sonuc = sadakat.kahve_ekle(self.musteri, self.latte)

        self.assertEqual(len(sonuc["kazanilan_hediyeler"]), 1)
        self.assertEqual(self.musteri.aktif_kahve_sayisi, 0)
        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 1)

    def test_en_eski_kahveler_harcanir(self):
        simdi = timezone.now()
        for gun_once in (5, 4, 3, 2, 1, 0):
            sadakat.kahve_ekle(self.musteri, self.latte, tarih=simdi - timedelta(days=gun_once))

        harcanan = self.musteri.icimler.filter(durum=KahveIcim.Durum.HARCANDI).order_by("tarih")
        kalan = self.musteri.aktif_icimler()

        self.assertEqual(harcanan.count(), 5)
        self.assertEqual(kalan.count(), 1)
        # En yeni kahve sayacta kalmali
        self.assertGreater(kalan.first().tarih, harcanan.last().tarih)

    def test_hediye_kahve_yeni_sayaci_baslatmaz(self):
        for _ in range(5):
            sadakat.kahve_ekle(self.musteri, self.latte)

        sonuc = sadakat.hediye_kullan(self.musteri, self.latte)

        self.assertIsNotNone(sonuc)
        self.assertEqual(self.musteri.aktif_kahve_sayisi, 0)
        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 0)
        self.assertEqual(sonuc["icim"].durum, KahveIcim.Durum.HEDIYE)
        self.assertIsNone(sonuc["icim"].son_gecerlilik)

    def test_hediye_yokken_kullanilamaz(self):
        self.assertIsNone(sadakat.hediye_kullan(self.musteri, self.latte))

    def test_hediye_kahve_toplam_icime_sayilmaz(self):
        for _ in range(5):
            sadakat.kahve_ekle(self.musteri, self.latte)
        sadakat.hediye_kullan(self.musteri, self.latte)

        self.assertEqual(self.musteri.toplam_icim_sayisi, 5)

    def test_admin_esigi_dusurunce_kural_hemen_gecerli(self):
        self.ayar.hediye_icin_kahve = 3
        self.ayar.save()

        for _ in range(3):
            sadakat.kahve_ekle(self.musteri, self.latte)

        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 1)

    def test_kart_ekrani_dogru_damgalari_verir(self):
        simdi = timezone.now()
        sadakat.kahve_ekle(self.musteri, self.latte, tarih=simdi - timedelta(days=6))
        sadakat.kahve_ekle(self.musteri, self.latte, tarih=simdi - timedelta(days=1))

        durum = sadakat.kart_durumu(self.musteri)

        self.assertEqual(len(durum["damgalar"]), 5)
        self.assertEqual(durum["aktif_sayi"], 2)
        self.assertEqual(durum["kalan"], 3)
        # 6 gun once icilen kahvenin 1 gunu kaldi -> soluyor
        self.assertTrue(durum["damgalar"][0]["sonuyor"])
        self.assertFalse(durum["damgalar"][1]["sonuyor"])

    def test_kart_okununca_sure_kendi_kendine_temizlenir(self):
        """Cron calismasa bile ekranda gorunen sayi dogru olmali."""
        sadakat.kahve_ekle(self.musteri, self.latte, tarih=timezone.now() - timedelta(days=10))

        durum = sadakat.kart_durumu(self.musteri)

        self.assertEqual(durum["aktif_sayi"], 0)


class MusteriKoduTesti(TestCase):
    def test_kodlar_benzersiz_ve_12_hane(self):
        kodlar = {KahveMusteri.objects.create(ad_soyad=f"M{i}").kod for i in range(25)}

        self.assertEqual(len(kodlar), 25)
        for kod in kodlar:
            self.assertEqual(len(kod), 12)
            self.assertTrue(kod.isdigit())


class SayfaTesti(TestCase):
    def setUp(self):
        self.ayar = KahveAyar.al()
        self.musteri = KahveMusteri.objects.create(ad_soyad="Kart Sahibi")
        Kahve.objects.create(ad="Espresso", fiyat=70, damga_veriyor=True)

    def test_menu_herkese_acik(self):
        self.assertEqual(self.client.get("/kahve/").status_code, 200)

    def test_web_de_musteri_girisi_yok(self):
        """Web'de kahve icin login/kart ekrani bulunmamali."""
        for yol in ("/kahve/giris/", "/kahve/kart/", "/kahve/oturum-ac/", "/kahve/cikis/"):
            with self.subTest(yol=yol):
                self.assertEqual(self.client.get(yol).status_code, 404)

    def test_musteri_karti_personel_ister(self):
        """QR karti artik sadece personel acabilir (admin'den link veriliyor)."""
        self.assertEqual(self.client.get(f"/kahve/k/{self.musteri.qr_token}/").status_code, 302)

    def test_personel_musteri_kartini_acabilir(self):
        User.objects.create_superuser("personel", "p@o.com", "gizli-sifre-123")
        self.client.login(username="personel", password="gizli-sifre-123")

        cevap = self.client.get(f"/kahve/k/{self.musteri.qr_token}/")

        self.assertEqual(cevap.status_code, 200)
        self.assertContains(cevap, "Kart Sahibi")

    def test_kasa_personel_ister(self):
        self.assertEqual(self.client.get("/kahve/kasa/").status_code, 302)

    def test_stok_anasayfasi_bozulmadi(self):
        """Kahve app'i eklenince mevcut sistem etkilenmemeli."""
        self.assertIn(self.client.get("/").status_code, (200, 302))


class CronTesti(TestCase):
    def setUp(self):
        self.ayar = KahveAyar.al()

    def test_anahtarsiz_reddedilir(self):
        self.assertEqual(self.client.get("/kahve/cron/gunluk-temizlik/").status_code, 403)

    def test_yanlis_anahtar_reddedilir(self):
        cevap = self.client.get("/kahve/cron/gunluk-temizlik/?anahtar=yanlis")

        self.assertEqual(cevap.status_code, 403)

    def test_dogru_anahtar_calisir(self):
        cevap = self.client.get(f"/kahve/cron/gunluk-temizlik/?anahtar={self.ayar.cron_anahtari}")

        self.assertEqual(cevap.status_code, 200)
        self.assertTrue(cevap.json()["ok"])

    def test_anahtar_baslikla_da_gonderilebilir(self):
        cevap = self.client.get(
            "/kahve/cron/gunluk-temizlik/", HTTP_X_KAHVE_KEY=self.ayar.cron_anahtari
        )

        self.assertEqual(cevap.status_code, 200)


class MobilApiTesti(TestCase):
    def setUp(self):
        self.ayar = KahveAyar.al()
        self.anahtar = self.ayar.mobil_api_anahtari
        Kahve.objects.create(ad="Latte", fiyat=90, icindekiler="Espresso\nSut", damga_veriyor=True)
        Kahve.objects.create(ad="Gizli", fiyat=50, aktif=False)

    def test_anahtarsiz_istek_reddedilir(self):
        self.assertEqual(self.client.get("/kahve/api/v1/menu/").status_code, 401)

    def test_yanlis_anahtar_reddedilir(self):
        cevap = self.client.get("/kahve/api/v1/menu/", HTTP_X_KAHVE_KEY="yanlis")

        self.assertEqual(cevap.status_code, 401)

    def test_menu_sadece_aktif_kahveleri_verir(self):
        cevap = self.client.get("/kahve/api/v1/menu/", HTTP_X_KAHVE_KEY=self.anahtar)

        self.assertEqual(cevap.status_code, 200)
        kahveler = cevap.json()["kahveler"]
        self.assertEqual(len(kahveler), 1)
        self.assertEqual(kahveler[0]["ad"], "Latte")
        self.assertEqual(kahveler[0]["icindekiler"], ["Espresso", "Sut"])

    def test_ayarlar_kurallari_verir(self):
        cevap = self.client.get("/kahve/api/v1/ayarlar/", HTTP_X_KAHVE_KEY=self.anahtar)

        govde = cevap.json()
        self.assertEqual(govde["hediye_icin_kahve"], self.ayar.hediye_icin_kahve)
        self.assertEqual(govde["gecerlilik_gun"], self.ayar.gecerlilik_gun)

    def test_kart_firebase_tokeni_ister(self):
        cevap = self.client.get("/kahve/api/v1/kart/", HTTP_X_KAHVE_KEY=self.anahtar)

        self.assertEqual(cevap.status_code, 401)


class KasaSepetiTesti(TestCase):
    """Kasa akisi: sepete ekle -> musteri baglar -> odeme -> kasa sifirlanir."""

    def setUp(self):
        self.ayar = KahveAyar.al()
        self.ayar.hediye_icin_kahve = 3
        self.ayar.save()
        User.objects.create_superuser("kasa", "kasa@ornek.com", "gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasa", password="gizli-sifre-123")

        self.musteri = KahveMusteri.objects.create(ad_soyad="Kasa Musterisi")
        self.latte = Kahve.objects.create(ad="Latte", fiyat=90, damga_veriyor=True)
        self.espresso = Kahve.objects.create(ad="Espresso", fiyat=70, damga_veriyor=True)
        self.ozel = Kahve.objects.create(
            ad="Ozel Harman", fiyat=150, hediye_gecerli=False, damga_veriyor=True
        )

    def _gonder(self, ad, govde=None, **kwargs):
        return self.client.post(
            reverse(f"kahve:{ad}", **kwargs), govde or {}, content_type="application/json"
        )

    def _sepet(self):
        return self.client.post(reverse("kahve:kasa-durum")).json()["sepet"]

    # --- sepet ---

    def test_kasa_ekrani_acilir(self):
        self.assertEqual(self.client.get(reverse("kahve:kasa")).status_code, 200)

    def test_sepete_ekleyip_toplam_hesaplanir(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        sepet = self._gonder("kasa-sepete-ekle", {"kahve_id": self.espresso.id}).json()["sepet"]

        self.assertEqual(len(sepet["satirlar"]), 2)
        self.assertEqual(sepet["toplam"], 90 * 2 + 70)
        self.assertEqual(sepet["fincan_adedi"], 3)

    def test_adet_degistirilir(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        sepet = self._gonder("kasa-adet", {"kahve_id": self.latte.id, "adet": 5}).json()["sepet"]

        self.assertEqual(sepet["toplam"], 450)

    def test_adet_sifira_dusunce_satir_silinir(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        sepet = self._gonder("kasa-adet", {"kahve_id": self.latte.id, "adet": 0}).json()["sepet"]

        self.assertEqual(sepet["satirlar"], [])

    def test_satir_silinir(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        sepet = self._gonder("kasa-satir-sil", {"kahve_id": self.latte.id}).json()["sepet"]

        self.assertEqual(sepet["toplam"], 0)

    def test_kasa_sifirlanir(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        sepet = self._gonder("kasa-sifirla").json()["sepet"]

        self.assertEqual(sepet["satirlar"], [])
        self.assertIsNone(sepet["musteri"])

    # --- musteri ---

    def test_barkodla_musteri_baglanir(self):
        sepet = self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod}).json()["sepet"]

        self.assertEqual(sepet["musteri"]["ad_soyad"], "Kasa Musterisi")

    def test_qr_ile_musteri_baglanir(self):
        adres = f"https://ornek.com/kahve/k/{self.musteri.qr_token}/"
        sepet = self._gonder("kasa-musteri-bul", {"kod": adres}).json()["sepet"]

        self.assertEqual(sepet["musteri"]["kod"], self.musteri.kod)

    def test_olmayan_kod_404(self):
        self.assertEqual(self._gonder("kasa-musteri-bul", {"kod": "000000000000"}).status_code, 404)

    def test_musteri_cikarilir(self):
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        sepet = self._gonder("kasa-musteri-cikar").json()["sepet"]

        self.assertIsNone(sepet["musteri"])

    # --- hediye ---

    def test_hediye_kullanilinca_tutar_dusar(self):
        HediyeKahve.objects.create(musteri=self.musteri)
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-adet", {"kahve_id": self.latte.id, "adet": 2})

        sepet = self._gonder("kasa-hediye", {"kahve_id": self.latte.id, "hediye_adet": 1}).json()["sepet"]

        self.assertEqual(sepet["toplam"], 90)  # iki latte, biri hediye
        self.assertEqual(sepet["hediye_adedi"], 1)

    def test_hediyeden_fazlasi_kullanilamaz(self):
        HediyeKahve.objects.create(musteri=self.musteri)
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-adet", {"kahve_id": self.latte.id, "adet": 3})

        sepet = self._gonder("kasa-hediye", {"kahve_id": self.latte.id, "hediye_adet": 3}).json()["sepet"]

        self.assertEqual(sepet["hediye_adedi"], 1, "bekleyen hediyeden fazlasi kullanilmamali")

    def test_hediyeye_kapali_kahve_hediye_olamaz(self):
        HediyeKahve.objects.create(musteri=self.musteri)
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.ozel.id})

        sepet = self._gonder("kasa-hediye", {"kahve_id": self.ozel.id, "hediye_adet": 1}).json()["sepet"]

        self.assertEqual(sepet["hediye_adedi"], 0)
        self.assertEqual(sepet["toplam"], 150)

    def test_musteri_cikinca_hediye_iptal_olur(self):
        HediyeKahve.objects.create(musteri=self.musteri)
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-hediye", {"kahve_id": self.latte.id, "hediye_adet": 1})

        sepet = self._gonder("kasa-musteri-cikar").json()["sepet"]

        self.assertEqual(sepet["toplam"], 90)

    # --- satis ---

    def test_nakit_satis(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "nakit"})

        self.assertEqual(cevap.status_code, 200)
        satis = KahveSatis.objects.get()
        self.assertEqual(satis.toplam, 90)
        self.assertEqual(satis.nakit_tutar, 90)
        self.assertEqual(satis.kart_tutar, 0)
        self.assertEqual(cevap.json()["sepet"]["satirlar"], [], "satis sonrasi kasa sifirlanmali")

    def test_kart_satisi(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.espresso.id})
        self._gonder("kasa-satis-tamamla", {"odeme_turu": "kart"})

        satis = KahveSatis.objects.get()
        self.assertEqual(satis.kart_tutar, 70)
        self.assertEqual(satis.nakit_tutar, 0)

    def test_parcali_satis(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})   # 90
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.espresso.id})  # 70

        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "parcali", "nakit": "100", "kart": "60"})

        self.assertEqual(cevap.status_code, 200)
        satis = KahveSatis.objects.get()
        self.assertEqual(satis.toplam, 160)
        self.assertEqual(satis.nakit_tutar, 100)
        self.assertEqual(satis.kart_tutar, 60)

    def test_parcali_tutar_tutmazsa_reddedilir(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})  # 90

        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "parcali", "nakit": "50", "kart": "20"})

        self.assertEqual(cevap.status_code, 400)
        self.assertFalse(KahveSatis.objects.exists())

    def test_bos_sepet_satilamaz(self):
        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "nakit"})

        self.assertEqual(cevap.status_code, 400)

    def test_gecersiz_odeme_turu_reddedilir(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})

        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "kripto"})

        self.assertEqual(cevap.status_code, 400)

    def test_kartsiz_satis_yapilabilir(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-satis-tamamla", {"odeme_turu": "nakit"})

        satis = KahveSatis.objects.get()
        self.assertIsNone(satis.musteri)
        self.assertEqual(KahveIcim.objects.count(), 0, "kartsiz satista damga yazilmamali")

    def test_musterili_satis_damgalari_yazar(self):
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-adet", {"kahve_id": self.latte.id, "adet": 2})

        self._gonder("kasa-satis-tamamla", {"odeme_turu": "nakit"})

        self.assertEqual(self.musteri.aktif_kahve_sayisi, 2)
        self.assertEqual(KahveIcim.objects.filter(satis__isnull=False).count(), 2)

    def test_esige_gelen_satis_hediye_kazandirir(self):
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-adet", {"kahve_id": self.latte.id, "adet": 3})  # esik 3

        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "kart"})

        self.assertEqual(cevap.json()["kazanilan_hediye"], 1)
        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 1)

    def test_hediyeli_satis_hediyeyi_harcar(self):
        HediyeKahve.objects.create(musteri=self.musteri)
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        self._gonder("kasa-hediye", {"kahve_id": self.latte.id, "hediye_adet": 1})

        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "nakit"})

        self.assertEqual(cevap.status_code, 200)
        satis = KahveSatis.objects.get()
        self.assertEqual(satis.toplam, 0)
        self.assertEqual(satis.hediye_adedi, 1)
        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 0)
        self.assertEqual(self.musteri.aktif_kahve_sayisi, 0, "hediye yeni sayac baslatmamali")

    def test_kasadan_musteri_acilir_ve_baglanir(self):
        sepet = self._gonder("kasa-musteri-ekle", {"ad_soyad": "Yeni Musteri"}).json()["sepet"]

        self.assertEqual(sepet["musteri"]["ad_soyad"], "Yeni Musteri")

    def test_personel_olmayan_kasaya_giremez(self):
        anonim = Client()

        self.assertEqual(anonim.post(reverse("kahve:kasa-sepete-ekle")).status_code, 302)

    def test_gunun_ozeti_satisla_artar(self):
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.latte.id})
        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "nakit"})

        gun = cevap.json()["gun"]
        self.assertEqual(gun["satis"], 1)
        self.assertEqual(float(gun["ciro"]), 90.0)


def _gorsel_uret(genislik=2400, yukseklik=1600, ad="test.jpg"):
    tampon = BytesIO()
    Image.new("RGB", (genislik, yukseklik), (120, 80, 50)).save(tampon, format="JPEG")
    return SimpleUploadedFile(ad, tampon.getvalue(), content_type="image/jpeg")


class GorselTesti(TestCase):
    """Yuklenen fotograflar kuculmeli ve arkalarinda cop birakmamali."""

    def setUp(self):
        self.medya = tempfile.mkdtemp()
        self.kapsam = override_settings(MEDIA_ROOT=self.medya)
        self.kapsam.enable()
        self.addCleanup(self.kapsam.disable)
        self.addCleanup(shutil.rmtree, self.medya, True)

    def test_buyuk_gorsel_kare_kirpilir_ve_kucultulur(self):
        """Menu ve mobil uygulama 1:1 gosteriyor; kirpmayi yuklerken yapiyoruz."""
        kahve = Kahve.objects.create(ad="Buyuk", fiyat=50, gorsel=_gorsel_uret(2400, 1600))

        with Image.open(kahve.gorsel.path) as resim:
            self.assertEqual(resim.width, resim.height, "kare olmali")
            self.assertEqual(resim.width, 1200, "en fazla 1200px")

    def test_dikey_gorsel_de_kare_olur(self):
        kahve = Kahve.objects.create(ad="Dikey", fiyat=50, gorsel=_gorsel_uret(800, 1600))

        with Image.open(kahve.gorsel.path) as resim:
            self.assertEqual((resim.width, resim.height), (800, 800), "kisa kenara gore kare")

    def test_kucuk_gorsel_kare_yapilir_ama_buyutulmez(self):
        kahve = Kahve.objects.create(ad="Kucuk", fiyat=50, gorsel=_gorsel_uret(600, 400))

        with Image.open(kahve.gorsel.path) as resim:
            self.assertEqual((resim.width, resim.height), (400, 400))

    def test_zaten_kare_ve_kucukse_dokunulmaz(self):
        kahve = Kahve.objects.create(ad="Kare", fiyat=50, gorsel=_gorsel_uret(500, 500))

        with Image.open(kahve.gorsel.path) as resim:
            self.assertEqual((resim.width, resim.height), (500, 500))

    def test_gorsel_degisince_eskisi_silinir(self):
        kahve = Kahve.objects.create(ad="Degisen", fiyat=50, gorsel=_gorsel_uret(ad="eski.jpg"))
        eski_yol = Path(kahve.gorsel.path)
        self.assertTrue(eski_yol.exists())

        kahve.gorsel = _gorsel_uret(ad="yeni.jpg")
        kahve.save()

        self.assertFalse(eski_yol.exists(), "eski dosya diskte kalmis")
        self.assertTrue(Path(kahve.gorsel.path).exists())

    def test_urun_silinince_gorseli_de_silinir(self):
        kahve = Kahve.objects.create(ad="Silinecek", fiyat=50, gorsel=_gorsel_uret())
        yol = Path(kahve.gorsel.path)

        kahve.delete()

        self.assertFalse(yol.exists())

    def test_toplu_silmede_de_gorseller_silinir(self):
        """Admin'deki toplu silme queryset.delete() cagirir, sinyal sart."""
        Kahve.objects.create(ad="Toplu 1", fiyat=50, gorsel=_gorsel_uret(ad="t1.jpg"))
        Kahve.objects.create(ad="Toplu 2", fiyat=50, gorsel=_gorsel_uret(ad="t2.jpg"))
        yollar = [Path(k.gorsel.path) for k in Kahve.objects.all()]

        Kahve.objects.all().delete()

        for yol in yollar:
            self.assertFalse(yol.exists(), f"{yol.name} diskte kalmis")

    def test_gorselsiz_urun_silinebilir(self):
        kahve = Kahve.objects.create(ad="Gorselsiz", fiyat=50)

        kahve.delete()  # hata firlatmamali

        self.assertEqual(Kahve.objects.count(), 0)

    def test_oksuz_dosya_komutla_temizlenir(self):
        kahve = Kahve.objects.create(ad="Bagli", fiyat=50, gorsel=_gorsel_uret(ad="bagli.jpg"))
        bagli = Path(kahve.gorsel.path)
        oksuz = bagli.parent / "kimsesiz.jpg"
        oksuz.write_bytes(b"cop")

        call_command("gorsel_temizle", "--sil", verbosity=0)

        self.assertFalse(oksuz.exists(), "oksuz dosya silinmemis")
        self.assertTrue(bagli.exists(), "bagli dosya yanlislikla silinmis")

    def test_kuru_calisma_dosyaya_dokunmaz(self):
        kahve = Kahve.objects.create(ad="Bagli", fiyat=50, gorsel=_gorsel_uret(ad="bagli.jpg"))
        oksuz = Path(kahve.gorsel.path).parent / "kimsesiz.jpg"
        oksuz.write_bytes(b"cop")

        call_command("gorsel_temizle", verbosity=0)

        self.assertTrue(oksuz.exists(), "--sil verilmeden dosya silinmis")


class DamgaBayragiTesti(TestCase):
    """Sadece "Hediye sayacına +1" acik urunler damga kazandirir."""

    def setUp(self):
        self.ayar = KahveAyar.al()
        self.ayar.hediye_icin_kahve = 5
        self.ayar.save()
        self.musteri = KahveMusteri.objects.create(ad_soyad="Damga Musterisi")
        self.kahve = Kahve.objects.create(ad="Latte", fiyat=90, damga_veriyor=True)
        self.kurabiye = Kahve.objects.create(ad="Kurabiye", fiyat=40, damga_veriyor=False)

    def test_varsayilan_kapali(self):
        """Yeni urun eklenince damga vermemeli; kahve olanlar elle acilir."""
        yeni = Kahve.objects.create(ad="Su", fiyat=15)

        self.assertFalse(yeni.damga_veriyor)

    def test_kahve_damga_verir(self):
        sadakat.kahve_ekle(self.musteri, self.kahve)

        self.assertEqual(self.musteri.aktif_kahve_sayisi, 1)

    def test_kurabiye_damga_vermez(self):
        sadakat.kahve_ekle(self.musteri, self.kurabiye)

        self.assertEqual(self.musteri.aktif_kahve_sayisi, 0)

    def test_kurabiye_gecmiste_yine_de_gorunur(self):
        """Damga vermese de satin alma kaydi kaybolmamali."""
        sonuc = sadakat.kahve_ekle(self.musteri, self.kurabiye)

        self.assertEqual(sonuc["icim"].durum, KahveIcim.Durum.SAYILMAZ)
        self.assertIsNone(sonuc["icim"].son_gecerlilik)
        self.assertEqual(self.musteri.icimler.count(), 1)

    def test_kurabiye_hediye_kazandirmaz(self):
        for _ in range(10):
            sadakat.kahve_ekle(self.musteri, self.kurabiye)

        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 0)

    def test_elle_yazilan_kahve_damga_verir(self):
        """Admin'deki 'kahve yaz' eyleminde urun secilmez, damga verilmeli."""
        sadakat.kahve_ekle(self.musteri, kahve=None)

        self.assertEqual(self.musteri.aktif_kahve_sayisi, 1)


class ToplaSatisDamgaTesti(TestCase):
    """Bir satista kac fincan varsa o kadar damga eklenir."""

    def setUp(self):
        self.ayar = KahveAyar.al()
        self.ayar.hediye_icin_kahve = 15
        self.ayar.save()
        User.objects.create_superuser("kasa", "k@o.com", "gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasa", password="gizli-sifre-123")
        self.musteri = KahveMusteri.objects.create(ad_soyad="Toplu Alan")
        self.kahve = Kahve.objects.create(ad="Latte", fiyat=90, damga_veriyor=True)
        self.kurabiye = Kahve.objects.create(ad="Kurabiye", fiyat=40, damga_veriyor=False)

    def _gonder(self, ad, govde=None):
        return self.client.post(reverse(f"kahve:{ad}"), govde or {}, content_type="application/json")

    def test_alti_kahve_alti_damga_yazar(self):
        """15 damgalik kartta 6 kahve alan musterinin 6'si dolar."""
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.kahve.id})
        self._gonder("kasa-adet", {"kahve_id": self.kahve.id, "adet": 6})

        self._gonder("kasa-satis-tamamla", {"odeme_turu": "nakit"})

        self.assertEqual(self.musteri.aktif_kahve_sayisi, 6)
        self.assertEqual(self.musteri.bekleyen_hediye_sayisi, 0, "15'e ulasmadi, hediye olmamali")

    def test_sepetteki_kurabiye_damgaya_sayilmaz(self):
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.kahve.id})
        self._gonder("kasa-adet", {"kahve_id": self.kahve.id, "adet": 2})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.kurabiye.id})
        sepet = self._gonder("kasa-adet", {"kahve_id": self.kurabiye.id, "adet": 3}).json()["sepet"]

        self.assertEqual(sepet["fincan_adedi"], 5)
        self.assertEqual(sepet["damga_adedi"], 2, "sadece kahveler damga vermeli")

        self._gonder("kasa-satis-tamamla", {"odeme_turu": "nakit"})

        self.assertEqual(self.musteri.aktif_kahve_sayisi, 2)
        self.assertEqual(self.musteri.icimler.count(), 5, "kurabiyeler de gecmise yazilmali")

    def test_esige_ulasan_toplu_satis_hediye_verir(self):
        self.ayar.hediye_icin_kahve = 5
        self.ayar.save()
        self._gonder("kasa-musteri-bul", {"kod": self.musteri.kod})
        self._gonder("kasa-sepete-ekle", {"kahve_id": self.kahve.id})
        self._gonder("kasa-adet", {"kahve_id": self.kahve.id, "adet": 12})

        cevap = self._gonder("kasa-satis-tamamla", {"odeme_turu": "kart"})

        self.assertEqual(cevap.json()["kazanilan_hediye"], 2, "12 kahve / 5 esik = 2 hediye")
        self.assertEqual(self.musteri.aktif_kahve_sayisi, 2, "artan 2 damga sayacta kalir")


class MusteriWebeGiremezTesti(TestCase):
    """Musteri hesaplari yalnizca mobil uygulamada yasar.

    KahveMusteri, django.contrib.auth.User'dan tamamen bagimsiz bir model ve
    web tarafinda musteri oturumu diye bir sey yok. Eski bir oturum anahtari
    tarayicida kalmis olsa bile hicbir kapiyi acmamali.
    """

    def setUp(self):
        self.musteri = KahveMusteri.objects.create(ad_soyad="Sadece Musteri", firebase_uid="fb-123")
        oturum = self.client.session
        oturum["kahve_musteri_id"] = self.musteri.id   # eski surumden kalma
        oturum.save()

    def test_eski_oturum_anahtari_ise_yaramaz(self):
        for yol in ("/kahve/kart/", "/kahve/giris/"):
            with self.subTest(yol=yol):
                self.assertEqual(self.client.get(yol).status_code, 404)

    def test_musteri_admin_paneline_giremez(self):
        cevap = self.client.get("/admin/", follow=False)

        self.assertEqual(cevap.status_code, 302)
        self.assertIn("/admin/login/", cevap["Location"])

    def test_musteri_kasaya_giremez(self):
        cevap = self.client.get(reverse("kahve:kasa"))

        self.assertEqual(cevap.status_code, 302)

    def test_musteri_baskasinin_kartini_goremez(self):
        self.assertEqual(
            self.client.get(f"/kahve/k/{self.musteri.qr_token}/").status_code, 302
        )

    def test_musteri_kasa_uclarini_kullanamaz(self):
        for uc in ("kasa-sepete-ekle", "kasa-musteri-bul", "kasa-satis-tamamla"):
            with self.subTest(uc=uc):
                self.assertEqual(self.client.post(reverse(f"kahve:{uc}")).status_code, 302)

    def test_musterinin_django_kullanicisi_yok(self):
        self.assertFalse(User.objects.filter(username=self.musteri.ad_soyad).exists())
        self.assertEqual(User.objects.count(), 0)


class YedekAlmaTesti(TestCase):
    """Urunleri disa aktar, sil, geri yukle."""

    def setUp(self):
        self.medya = tempfile.mkdtemp()
        self.kapsam = override_settings(MEDIA_ROOT=self.medya)
        self.kapsam.enable()
        self.addCleanup(self.kapsam.disable)
        self.addCleanup(shutil.rmtree, self.medya, True)

        self.yedek = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.yedek, True)

        Kahve.objects.create(
            ad="Latte", fiyat=90, aciklama="Ipeksi sut kopugu.",
            icindekiler="Espresso\nSut", sira=1,
            damga_veriyor=True, hediye_gecerli=True,
            gorsel=_gorsel_uret(600, 400, "latte.jpg"),
        )
        Kahve.objects.create(
            ad="Kurabiye", fiyat=45, sira=2,
            damga_veriyor=False, hediye_gecerli=False,
        )

    def _disa_aktar(self):
        call_command("kahve_disa_aktar", klasor=self.yedek, verbosity=0)
        return Path(self.yedek)

    def test_yedek_dosyalari_olusur(self):
        klasor = self._disa_aktar()

        self.assertTrue((klasor / "urunler.csv").is_file())
        self.assertTrue((klasor / "tum-veri.json").is_file())
        self.assertTrue((klasor / "gorseller" / "latte.jpg").is_file())

    def test_silinen_urunler_geri_yuklenir(self):
        klasor = self._disa_aktar()
        Kahve.objects.all().delete()
        self.assertEqual(Kahve.objects.count(), 0)

        call_command("kahve_ice_aktar", str(klasor / "urunler.csv"), "--uygula", verbosity=0)

        self.assertEqual(Kahve.objects.count(), 2)
        latte = Kahve.objects.get(ad="Latte")
        self.assertEqual(latte.fiyat, 90)
        self.assertEqual(latte.icindekiler_listesi, ["Espresso", "Sut"])
        self.assertTrue(latte.damga_veriyor)

    def test_bayraklar_korunur(self):
        klasor = self._disa_aktar()
        Kahve.objects.all().delete()

        call_command("kahve_ice_aktar", str(klasor / "urunler.csv"), "--uygula", verbosity=0)

        kurabiye = Kahve.objects.get(ad="Kurabiye")
        self.assertFalse(kurabiye.damga_veriyor, "kurabiye damga vermemeli")
        self.assertFalse(kurabiye.hediye_gecerli)

    def test_gorsel_de_geri_gelir(self):
        klasor = self._disa_aktar()
        Kahve.objects.all().delete()

        call_command("kahve_ice_aktar", str(klasor / "urunler.csv"), "--uygula", verbosity=0)

        self.assertTrue(Kahve.objects.get(ad="Latte").gorsel)

    def test_kuru_calisma_veriyi_degistirmez(self):
        klasor = self._disa_aktar()
        Kahve.objects.all().delete()

        call_command("kahve_ice_aktar", str(klasor / "urunler.csv"), verbosity=0)

        self.assertEqual(Kahve.objects.count(), 0, "--uygula verilmeden kayit acilmamali")

    def test_mevcut_urun_guncellenir_kopyalanmaz(self):
        """Excel'de fiyat degistirip geri yuklemek en sik kullanim."""
        klasor = self._disa_aktar()
        csv_yolu = klasor / "urunler.csv"
        csv_yolu.write_text(
            csv_yolu.read_text(encoding="utf-8-sig").replace("Latte,90.00", "Latte,120.00"),
            encoding="utf-8-sig",
        )

        call_command("kahve_ice_aktar", str(csv_yolu), "--uygula", verbosity=0)

        self.assertEqual(Kahve.objects.filter(ad="Latte").count(), 1, "kopya urun olusmamali")
        self.assertEqual(Kahve.objects.get(ad="Latte").fiyat, 120)

    def test_bozuk_satir_atlanir_digerleri_yuklenir(self):
        klasor = self._disa_aktar()
        csv_yolu = klasor / "urunler.csv"
        with csv_yolu.open("a", encoding="utf-8-sig") as dosya:
            dosya.write("Bozuk Urun,fiyat-degil,,,0,evet,hayir,evet,\n")
        Kahve.objects.all().delete()

        call_command("kahve_ice_aktar", str(csv_yolu), "--uygula", verbosity=0)

        self.assertEqual(Kahve.objects.count(), 2)
        self.assertFalse(Kahve.objects.filter(ad="Bozuk Urun").exists())

    def test_tam_veri_json_ile_her_sey_geri_gelir(self):
        musteri = KahveMusteri.objects.create(ad_soyad="Yedek Musterisi")
        sadakat.kahve_ekle(musteri, Kahve.objects.get(ad="Latte"))
        klasor = self._disa_aktar()

        icerik = (klasor / "tum-veri.json").read_text(encoding="utf-8")

        self.assertIn("kahve.kahvemusteri", icerik)
        self.assertIn("kahve.kahveicim", icerik)
        self.assertIn("Yedek Musterisi", icerik)


class KahveBorcaYazmaTesti(TestCase):
    """Kahve satisi kirtasiye tarafindaki borc hanesine yazilir.

    Iki tezgah ayni musteri kaydini kullanir: kahve borcu da ayni yere isler.
    """

    def setUp(self):
        User.objects.create_superuser("kasiyer", "k@o.com", "gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")
        self.kahve = Kahve.objects.create(ad="Latte", fiyat=80, damga_veriyor=True)
        self.musteri = Musteri.objects.create(
            isim_soyisim="Borçlu Müşteri", Cep_Telefonu=5551112233, borc=Decimal("20.00")
        )

    def _sepete_ekle(self, adet=1):
        for _ in range(adet):
            self.client.post(
                reverse("kahve:kasa-sepete-ekle"),
                data=json.dumps({"kahve_id": self.kahve.id}),
                content_type="application/json",
            )

    def test_borca_yazinca_musterinin_borcu_artar(self):
        self._sepete_ekle(2)

        cevap = self.client.post(
            reverse("kahve:kasa-satis-tamamla"),
            data=json.dumps({"odeme_turu": "borc", "borc_musteri_id": self.musteri.id}),
            content_type="application/json",
        )

        self.assertEqual(cevap.status_code, 200)
        self.musteri.refresh_from_db()
        self.assertEqual(self.musteri.borc, Decimal("180.00"), "20 + 2x80")

    def test_borc_hareketi_alinanlari_yazar(self):
        self._sepete_ekle(2)

        self.client.post(
            reverse("kahve:kasa-satis-tamamla"),
            data=json.dumps({
                "odeme_turu": "borc",
                "borc_musteri_id": self.musteri.id,
                "not": "cumartesi ödeyecek",
            }),
            content_type="application/json",
        )

        hareket = BorcHareketi.objects.get(musteri=self.musteri)
        self.assertEqual(hareket.tutar, Decimal("160.00"))
        self.assertEqual(hareket.onceki_borc, Decimal("20.00"))
        self.assertIn("2x Latte", hareket.aciklama)
        self.assertIn("cumartesi ödeyecek", hareket.aciklama)

    def test_musteri_secilmeden_borca_yazilamaz(self):
        self._sepete_ekle(1)

        cevap = self.client.post(
            reverse("kahve:kasa-satis-tamamla"),
            data=json.dumps({"odeme_turu": "borc"}),
            content_type="application/json",
        )

        self.assertEqual(cevap.status_code, 400)
        self.assertEqual(BorcHareketi.objects.count(), 0)
        self.assertEqual(Musteri.objects.get(pk=self.musteri.pk).borc, Decimal("20.00"))

    def test_borc_satisi_kasaya_para_yazmaz(self):
        """Borca yazilan tutar ciroya girer ama nakit/kart hanesine girmez."""
        self._sepete_ekle(1)

        self.client.post(
            reverse("kahve:kasa-satis-tamamla"),
            data=json.dumps({"odeme_turu": "borc", "borc_musteri_id": self.musteri.id}),
            content_type="application/json",
        )

        satis = KahveSatis.objects.get()
        self.assertEqual(satis.nakit_tutar, Decimal("0.00"))
        self.assertEqual(satis.kart_tutar, Decimal("0.00"))
        self.assertEqual(satis.toplam, Decimal("80.00"))
        gun = kasa_sepeti.gunun_ozeti()
        self.assertEqual(gun["borc"], Decimal("80.00"))
        self.assertEqual(gun["nakit"], Decimal("0.00"))

    def test_damga_yine_islenir(self):
        """Borca yazmak sadakati etkilemez: kahve icildi, damga hak edildi."""
        kart_musterisi = KahveMusteri.objects.create(ad_soyad="Kart Sahibi", firebase_uid="fb-1")
        self._sepete_ekle(1)
        self.client.post(
            reverse("kahve:kasa-musteri-bul"),
            data=json.dumps({"kod": kart_musterisi.kod}),
            content_type="application/json",
        )

        self.client.post(
            reverse("kahve:kasa-satis-tamamla"),
            data=json.dumps({"odeme_turu": "borc", "borc_musteri_id": self.musteri.id}),
            content_type="application/json",
        )

        self.assertEqual(
            KahveIcim.objects.filter(musteri=kart_musterisi, durum=KahveIcim.Durum.AKTIF).count(), 1
        )

    def test_musteri_arama_borcu_da_dondurur(self):
        cevap = self.client.get(reverse("kahve:kasa-borc-musterileri"), {"q": "Borçlu"})

        veri = cevap.json()
        self.assertEqual(len(veri["musteriler"]), 1)
        self.assertEqual(veri["musteriler"][0]["ad"], "Borçlu Müşteri")
        self.assertEqual(veri["musteriler"][0]["borc"], 20.0)

    def test_musteri_aramaya_personel_olmayan_giremez(self):
        anonim = Client()

        self.assertEqual(anonim.get(reverse("kahve:kasa-borc-musterileri")).status_code, 302)


class KasaSayfasiTesti(TestCase):
    """Sayfanin KENDISI calisir mi.

    Onceden sadece JSON uclari sinaniyordu; sepet/odeme panelinin HTML'i
    sablondan dusmustu ve testler bunu goremedi. Kasa kullanilamaz haldeydi.
    """

    # kasa.html icindeki JS bu id'leri arar; biri eksikse ekran sessizce bozulur
    GEREKLI_IDLER = [
        "khKod", "khMusteri", "khSatirlar", "khBosSepet", "khToplam",
        "khOdemeAc", "khSifirla", "khOdemePanel", "khVazgec", "khOnayla",
        "khParcali", "khParcaliNot", "khNakit", "khKart",
        "khIndirim", "khIndirimUygula", "khIndirimOzet",
        "khGunSatis", "khGunCiro", "khGunNakit", "khGunKart", "khGunIndirim", "khMenu",
    ]

    def setUp(self):
        User.objects.create_superuser("kasiyer", "k@o.com", "gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")
        menu_verisi.yukle(uygula=True, kahvelere_damga=True)

    def test_js_nin_aradigi_her_eleman_sayfada_var(self):
        cevap = self.client.get(reverse("kahve:kasa"))
        govde = cevap.content.decode()

        for id_ in self.GEREKLI_IDLER:
            with self.subTest(id=id_):
                self.assertIn(f'id="{id_}"', govde)

    def test_odeme_turlerinin_ucu_de_var(self):
        govde = self.client.get(reverse("kahve:kasa")).content.decode()

        for tur in ("nakit", "kart", "parcali"):
            with self.subTest(tur=tur):
                self.assertIn(f'data-odeme="{tur}"', govde)

    def test_urunler_tiklanabilir_ve_stilli_cikar(self):
        """Butonlar CSS'i olan sinifi kullanmali; yoksa duz beyaz etiket gorunur."""
        govde = self.client.get(reverse("kahve:kasa")).content.decode()

        self.assertIn('class="kh-urun"', govde)
        self.assertIn("data-kahve=", govde)
        self.assertIn(".kh-urun {", govde, "kh-urun icin stil tanimi da olmali")
        self.assertNotIn("kh-sec__ad", govde, "CSS'i olmayan eski sinif kalmamali")

    def test_gorseli_olmayan_urun_halka_motifine_duser(self):
        govde = self.client.get(reverse("kahve:kasa")).content.decode()

        self.assertIn("kh-urun__bos", govde)


class MenuYuklemeTesti(TestCase):
    """Menu verisini kuran komut. Web ekrani 2026-08-30'da kaldirildi."""

    def test_kuru_calisma_kayit_acmaz(self):
        menu_verisi.yukle(uygula=False)

        self.assertEqual(Kahve.objects.count(), 0, "kuru calisma hicbir sey yazmamali")

    def test_menuyu_kurar(self):
        menu_verisi.yukle(uygula=True, kahvelere_damga=True)

        self.assertEqual(Kahve.objects.count(), 29)
        self.assertTrue(KahveKategori.objects.filter(ad="Sıcak İçecekler").exists())
        self.assertTrue(KahveKategori.objects.filter(ad="Soğuk İçecekler").exists())
        self.assertEqual(Kahve.objects.get(ad="Espresso").fiyat, 70)

    def test_damga_secenegi_kahvelere_uygulanir(self):
        menu_verisi.yukle(uygula=True, kahvelere_damga=True)

        self.assertTrue(Kahve.objects.get(ad="Latte").damga_veriyor)
        self.assertFalse(Kahve.objects.get(ad="Çay").damga_veriyor, "çay damga vermemeli")
        self.assertFalse(Kahve.objects.get(ad="Şurup").damga_veriyor)

    def test_damga_secilmezse_hepsi_kapali(self):
        menu_verisi.yukle(uygula=True)

        self.assertFalse(Kahve.objects.get(ad="Latte").damga_veriyor)

    def test_tekrar_calistirinca_ayarlar_korunur(self):
        """En onemli garanti: fiyat guncellenir, kullanicinin ayarlari bozulmaz."""
        menu_verisi.yukle(uygula=True)
        cay = Kahve.objects.get(ad="Çay")
        cay.damga_veriyor = True
        cay.aciklama = "Demlik çayı"
        cay.save()

        menu_verisi.yukle(uygula=True, kahvelere_damga=True)

        cay.refresh_from_db()
        self.assertTrue(cay.damga_veriyor, "işaretlenen +1 korunmalı")
        self.assertEqual(cay.aciklama, "Demlik çayı", "açıklama korunmalı")
        self.assertEqual(Kahve.objects.count(), 29, "kopya ürün oluşmamalı")

    def test_komut_da_ayni_sonucu_verir(self):
        call_command("kahve_menu_yukle", "--uygula", verbosity=0)

        self.assertEqual(Kahve.objects.count(), 29)

    def test_menu_yukle_sayfasi_artik_yok(self):
        """Kullanici istedi: menu bir kere yuklendi, ekran kaldirildi."""
        with self.assertRaises(NoReverseMatch):
            reverse("kahve:kasa-menu-yukle")


class SiralamaTesti(TestCase):
    """Once kategori sirasi, sonra kategori icinde urun sirasi.

    Menu, kasa ekrani ve mobil API ayni sirayi kullaniyor; sira modelin
    Meta.ordering'inden geliyor, her ekranda ayri ayri siralanmiyor.
    """

    def setUp(self):
        self.sicak = KahveKategori.objects.create(ad="Sıcak", sira=0)
        self.soguk = KahveKategori.objects.create(ad="Soğuk", sira=1)
        self.ekstra = KahveKategori.objects.create(ad="Ekstra", sira=2)
        # Bilerek karisik yaratiliyor: siralamayi kayit sirasi degil alanlar belirlemeli
        Kahve.objects.create(ad="Sos", fiyat=10, kategori=self.ekstra, sira=1)
        Kahve.objects.create(ad="Iced Latte", fiyat=80, kategori=self.soguk, sira=2)
        Kahve.objects.create(ad="Latte", fiyat=80, kategori=self.sicak, sira=2)
        Kahve.objects.create(ad="Espresso", fiyat=70, kategori=self.sicak, sira=1)
        Kahve.objects.create(ad="Iced Americano", fiyat=70, kategori=self.soguk, sira=1)

    def test_once_kategori_sirasi_sonra_urun_sirasi(self):
        adlar = list(Kahve.objects.values_list("ad", flat=True))

        self.assertEqual(
            adlar,
            ["Espresso", "Latte", "Iced Americano", "Iced Latte", "Sos"],
        )

    def test_kategori_sirasi_degisince_menu_de_degisir(self):
        self.ekstra.sira = -1 if False else 0
        self.sicak.sira = 5
        self.sicak.save()
        self.ekstra.save()

        ilk = Kahve.objects.first()

        self.assertEqual(ilk.ad, "Sos", "sırası öne alınan kategori başa geçmeli")

    def test_yeni_urun_kategorisinin_sonuna_gider(self):
        """Sira bos birakilinca urun listenin BASINA ziplamamali."""
        yeni = Kahve.objects.create(ad="Mocha", fiyat=100, kategori=self.sicak)

        self.assertEqual(yeni.sira, 3, "kategorideki en büyük sıra + 1")
        sicak_adlari = [k.ad for k in Kahve.objects.filter(kategori=self.sicak)]
        self.assertEqual(sicak_adlari, ["Espresso", "Latte", "Mocha"])

    def test_elle_verilen_sira_korunur(self):
        yeni = Kahve.objects.create(ad="Türk Kahvesi", fiyat=40, kategori=self.sicak, sira=1)

        self.assertEqual(yeni.sira, 1, "açıkça yazılan sıraya dokunulmamalı")

    def test_kategorisiz_urun_en_sonda(self):
        """nulls_last olmadan SQLite basa, PostgreSQL sona koyuyordu.

        Yereldeki sira canlidakiyle ayni olsun diye Meta.ordering'de
        acikca yaziliyor.
        """
        Kahve.objects.create(ad="Kategorisiz", fiyat=5, sira=1)

        self.assertEqual(Kahve.objects.last().ad, "Kategorisiz")

    def test_menu_sayfasi_ayni_sirayi_gosterir(self):
        govde = Client().get(reverse("kahve:menu")).content.decode()

        self.assertLess(govde.index("Sıcak"), govde.index("Soğuk"))
        self.assertLess(govde.index("Soğuk"), govde.index("Ekstra"))
        self.assertLess(govde.index("Espresso"), govde.index("Latte"))

    def test_mobil_api_ayni_sirayi_dondurur(self):
        ayar = KahveAyar.al()
        ayar.mobil_api_anahtari = "test-anahtari"
        ayar.save()

        cevap = Client().get(reverse("kahve:api-menu"), HTTP_X_KAHVE_KEY="test-anahtari")

        adlar = [k["ad"] for k in cevap.json()["kahveler"]]
        self.assertEqual(adlar[0], "Espresso")
        self.assertEqual(adlar[-1], "Sos")


class KahveIndirimTesti(TestCase):
    """Kahve kasasinda ozel indirim. Kirtasiyedekiyle ayni kural, ayri sepet."""

    def setUp(self):
        User.objects.create_superuser("kasiyer", "k@o.com", "gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")
        self.kahve = Kahve.objects.create(ad="Latte", fiyat=100, damga_veriyor=True)
        self.musteri = Musteri.objects.create(
            isim_soyisim="Veresiye", Cep_Telefonu=5551112233, borc=Decimal("0")
        )

    def _uc(self, ad, **govde):
        return self.client.post(
            reverse(f"kahve:{ad}"), data=json.dumps(govde), content_type="application/json"
        )

    def _sepete(self, adet=1):
        for _ in range(adet):
            self._uc("kasa-sepete-ekle", kahve_id=self.kahve.id)

    def test_tl_indirimi_toplami_duser(self):
        self._sepete(2)                                  # 200 ₺

        sepet = self._uc("kasa-indirim", tur="tl", deger="30").json()["sepet"]

        self.assertEqual(sepet["ara_toplam"], 200.0)
        self.assertEqual(sepet["indirim"], 30.0)
        self.assertEqual(sepet["toplam"], 170.0)

    def test_yuzde_indirimi(self):
        self._sepete(2)

        sepet = self._uc("kasa-indirim", tur="yuzde", deger="25").json()["sepet"]

        self.assertEqual(sepet["toplam"], 150.0)

    def test_satis_indirimli_kaydedilir(self):
        self._sepete(2)
        self._uc("kasa-indirim", tur="tl", deger="30")

        self._uc("kasa-satis-tamamla", odeme_turu="nakit")

        satis = KahveSatis.objects.get()
        self.assertEqual(satis.toplam, Decimal("170.00"))
        self.assertEqual(satis.indirim_tutari, Decimal("30.00"))
        self.assertEqual(satis.nakit_tutar, Decimal("170.00"))
        self.assertEqual(satis.ara_toplam, Decimal("200.00"))

    def test_satis_bitince_indirim_temizlenir(self):
        self._sepete(1)
        self._uc("kasa-indirim", tur="tl", deger="30")
        self._uc("kasa-satis-tamamla", odeme_turu="nakit")

        self._sepete(1)
        sepet = self._uc("kasa-durum").json()["sepet"]

        self.assertEqual(sepet["indirim"], 0.0)
        self.assertEqual(sepet["toplam"], 100.0)

    def test_kasa_sifirlayinca_indirim_gider(self):
        self._sepete(1)
        self._uc("kasa-indirim", tur="tl", deger="30")

        self._uc("kasa-sifirla")
        self._sepete(1)
        sepet = self._uc("kasa-durum").json()["sepet"]

        self.assertEqual(sepet["indirim"], 0.0)

    def test_indirim_hediyeden_sonra_uygulanir(self):
        """Bedava verilen fincandan ayrica indirim yapilmaz."""
        kart = KahveMusteri.objects.create(ad_soyad="Kart", firebase_uid="fb-9")
        for _ in range(5):
            sadakat.kahve_ekle(kart, self.kahve)
        self._sepete(2)                                  # 200 ₺
        self._uc("kasa-musteri-bul", kod=kart.kod)
        self._uc("kasa-hediye", kahve_id=self.kahve.id, hediye_adet=1)   # 100 ₺ kaldi

        sepet = self._uc("kasa-indirim", tur="yuzde", deger="10").json()["sepet"]

        self.assertEqual(sepet["ara_toplam"], 100.0, "hediye düşülmüş tutar")
        self.assertEqual(sepet["indirim"], 10.0)
        self.assertEqual(sepet["toplam"], 90.0)

    def test_borca_yazmada_indirimli_tutar(self):
        self._sepete(2)
        self._uc("kasa-indirim", tur="tl", deger="50")

        self._uc("kasa-satis-tamamla", odeme_turu="borc", borc_musteri_id=self.musteri.id)

        self.musteri.refresh_from_db()
        self.assertEqual(self.musteri.borc, Decimal("150.00"))
        self.assertIn("İndirim", BorcHareketi.objects.get().aciklama)

    def test_toplami_asan_indirim_eksiye_dusurmez(self):
        self._sepete(1)

        sepet = self._uc("kasa-indirim", tur="tl", deger="500").json()["sepet"]

        self.assertEqual(sepet["toplam"], 0.0)
        self.assertEqual(sepet["indirim"], 100.0)

    def test_yuzde_yuzden_buyuk_reddedilir(self):
        self._sepete(1)

        cevap = self._uc("kasa-indirim", tur="yuzde", deger="150")

        self.assertEqual(cevap.status_code, 400)

    def test_gunun_ozetinde_indirim_toplami(self):
        self._sepete(2)
        self._uc("kasa-indirim", tur="tl", deger="30")
        self._uc("kasa-satis-tamamla", odeme_turu="nakit")

        gun = kasa_sepeti.gunun_ozeti()

        self.assertEqual(gun["indirim"], Decimal("30.00"))
        self.assertEqual(gun["ciro"], Decimal("170.00"), "ciro gerçekte alınan para")

    def test_iki_tezgahin_indirimi_birbirine_karismaz(self):
        """Kirtasiye ve kahve ayri oturum kutusu kullaniyor."""
        self._sepete(1)
        self._uc("kasa-indirim", tur="tl", deger="40")

        kirtasiye = self.client.get(reverse("modern-urun-ara"))

        self.assertNotIn('id="indirim-kaldir"', kirtasiye.content.decode())
        self.assertEqual(self._uc("kasa-durum").json()["sepet"]["indirim"], 40.0)

    def test_personel_olmayan_indirim_veremez(self):
        anonim = Client()

        self.assertEqual(anonim.post(reverse("kahve:kasa-indirim")).status_code, 302)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class GorselSikistirmaTesti(TestCase):
    """Fotograflar JPEG'e cevrilip kucultuluyor mu.

    Eskiden "zaten kare ve yeterince kucuk" diye erken donuyordu: 1024x1024
    PNG'ler oldugu gibi kaliyordu, 30 urunluk menu mobilde 50 MB indiriyordu.
    """

    def _png(self, ad="foto.png", olcu=(1024, 1024), duz=True):
        """Duz renk ya da fotografa benzer gradyan uretir.

        Duz renkli sentetik gorselde PNG zaten kucuk; boyut kazancini olcmek
        icin gercek fotograflar gibi gecisli bir gorsel gerekiyor.
        """
        resim = Image.new("RGB", olcu, (120, 80, 40))
        if not duz:
            en, boy = olcu
            pik = resim.load()
            for y in range(boy):
                for x in range(en):
                    pik[x, y] = ((x * 255) // en, (y * 255) // boy, ((x + y) * 255) // (en + boy))
        tampon = BytesIO()
        resim.save(tampon, format="PNG")
        return SimpleUploadedFile(ad, tampon.getvalue(), content_type="image/png")

    def test_kare_png_de_jpeg_e_cevrilir(self):
        """Asil hata buydu: kare ve kucuk olan dosyaya hic dokunulmuyordu."""
        kahve = Kahve.objects.create(ad="Espresso", fiyat=70, gorsel=self._png())

        kahve.refresh_from_db()
        self.assertTrue(kahve.gorsel.name.endswith(".jpg"))
        with Image.open(kahve.gorsel.path) as resim:
            self.assertEqual(resim.format, "JPEG")

    def test_fotografta_dosya_kucuyor(self):
        kaynak = self._png(duz=False)
        onceki = len(kaynak.read())
        kaynak.seek(0)

        kahve = Kahve.objects.create(ad="Latte", fiyat=80, gorsel=kaynak)

        self.assertLess(os.path.getsize(kahve.gorsel.path), onceki)

    def test_eski_png_dosyasi_siliniyor(self):
        kahve = Kahve.objects.create(ad="Mocha", fiyat=100, gorsel=self._png("mocha.png"))

        klasor = Path(kahve.gorsel.path).parent
        kalanlar = [d.name for d in klasor.iterdir() if d.name.startswith("mocha")]
        self.assertTrue(all(d.endswith(".jpg") for d in kalanlar), kalanlar)

    def test_dikdortgen_kare_kirpiliyor(self):
        kahve = Kahve.objects.create(
            ad="Americano", fiyat=70, gorsel=self._png("genis.png", olcu=(1600, 900))
        )

        with Image.open(kahve.gorsel.path) as resim:
            self.assertEqual(resim.width, resim.height)
            self.assertLessEqual(resim.width, 1200)

    def test_saydam_gorsel_beyaza_yatiyor(self):
        tampon = BytesIO()
        Image.new("RGBA", (800, 800), (255, 0, 0, 0)).save(tampon, format="PNG")
        saydam = SimpleUploadedFile("saydam.png", tampon.getvalue(), content_type="image/png")

        kahve = Kahve.objects.create(ad="Çay", fiyat=20, gorsel=saydam)

        with Image.open(kahve.gorsel.path) as resim:
            self.assertEqual(resim.mode, "RGB")
            self.assertEqual(resim.getpixel((10, 10)), (255, 255, 255))

    def test_komut_kuru_calisma_dosyaya_dokunmaz(self):
        kahve = Kahve.objects.create(ad="Filtre", fiyat=60, gorsel=self._png())
        onceki = os.path.getsize(kahve.gorsel.path)

        call_command("kahve_gorsel_sikistir", verbosity=0, stdout=StringIO())

        self.assertEqual(os.path.getsize(kahve.gorsel.path), onceki)
