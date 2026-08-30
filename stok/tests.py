"""Sepet miktar guncelleme testleri.

Bu uc nokta canli kasada kullaniliyor: miktar alani <select> iken gecersiz
deger gelmesi imkansizdi, <input type=number> olunca mumkun hale geldi.
Testler o sinirlari koruyor.

Calistirmak icin:
    python manage.py test stok
"""

import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase

from .models import Liste_Grup, SepetUrun, Stok, UrunGruplari


class MiktarGuncellemeTesti(TestCase):
    def setUp(self):
        self.sifre = "kasa-sifresi-123"
        self.kullanici = User.objects.create_user("kasa", password=self.sifre)
        self.baskasi = User.objects.create_user("baskasi", password=self.sifre)

        self.urun = Stok.objects.create(Urun_Adi="Test Urun", Barkod=9990000000001, Tutar=25)
        self.sepet = SepetUrun.objects.create(user=self.kullanici, urun=self.urun, miktar=2)

        self.client.login(username="kasa", password=self.sifre)

    def _adres(self, sepet_id=None):
        return f"/urun_miktar_guncelle/{sepet_id or self.sepet.id}/"

    def test_gecerli_miktar_kaydedilir(self):
        cevap = self.client.post(self._adres(), {"miktar": "7"})

        self.assertEqual(cevap.status_code, 200)
        self.assertTrue(cevap.json()["success"])
        self.sepet.refresh_from_db()
        self.assertEqual(self.sepet.miktar, 7)

    def test_bos_miktar_500_vermez(self):
        """Sayi alani bosaltilabildigi icin bu yol artik erisilebilir."""
        cevap = self.client.post(self._adres(), {"miktar": ""})

        self.assertEqual(cevap.status_code, 400)
        self.assertFalse(cevap.json()["success"])
        self.sepet.refresh_from_db()
        self.assertEqual(self.sepet.miktar, 2, "gecersiz istek miktari degistirmemeli")

    def test_sayi_olmayan_miktar_reddedilir(self):
        cevap = self.client.post(self._adres(), {"miktar": "abc"})

        self.assertEqual(cevap.status_code, 400)

    def test_sifir_ve_negatif_reddedilir(self):
        for deger in ("0", "-3"):
            with self.subTest(miktar=deger):
                cevap = self.client.post(self._adres(), {"miktar": deger})

                self.assertEqual(cevap.status_code, 400)
                self.sepet.refresh_from_db()
                self.assertEqual(self.sepet.miktar, 2)

    def test_miktar_alani_hic_gonderilmezse(self):
        cevap = self.client.post(self._adres(), {})

        self.assertEqual(cevap.status_code, 400)

    def test_baskasinin_sepetine_dokunulamaz(self):
        digeri = SepetUrun.objects.create(user=self.baskasi, urun=self.urun, miktar=5)

        cevap = self.client.post(self._adres(digeri.id), {"miktar": "99"})

        self.assertEqual(cevap.status_code, 404)
        digeri.refresh_from_db()
        self.assertEqual(digeri.miktar, 5)

    def test_giris_yapmadan_kullanilamaz(self):
        self.client.logout()

        cevap = self.client.post(self._adres(), {"miktar": "9"})

        self.assertEqual(cevap.status_code, 302)
        self.assertIn("/", cevap["Location"])
        self.sepet.refresh_from_db()
        self.assertEqual(self.sepet.miktar, 2)

    def test_get_ile_cagrilamaz(self):
        cevap = self.client.get(self._adres())

        self.assertEqual(cevap.status_code, 405)

    def test_olmayan_sepet_urunu_404(self):
        cevap = self.client.post(self._adres(999999), {"miktar": "3"})

        self.assertEqual(cevap.status_code, 404)


class SepetSayfasiTesti(TestCase):
    def setUp(self):
        self.sifre = "kasa-sifresi-123"
        self.kullanici = User.objects.create_user("kasa", password=self.sifre)
        self.client.login(username="kasa", password=self.sifre)
        for i in range(12):
            urun = Stok.objects.create(Urun_Adi=f"Urun {i}", Barkod=9990000001000 + i, Tutar=10)
            SepetUrun.objects.create(user=self.kullanici, urun=urun, miktar=2)

    def test_sayfa_acilir(self):
        self.assertEqual(self.client.get("/modern-urun-ara/").status_code, 200)

    def test_miktar_alani_sayi_girisi_olarak_cizilir(self):
        """1000 secenekli dropdown geri gelmesin: sayfa sisip tarayiciyi kilitliyordu."""
        icerik = self.client.get("/modern-urun-ara/").content

        self.assertEqual(icerik.count(b"<option"), 0)
        self.assertEqual(icerik.count(b'type="number" name="miktar"'), 12)

    def test_sepet_sorgu_sayisi_urun_sayisiyla_buyumez(self):
        """select_related olmadan her sepet satiri ek bir sorgu aciyordu."""
        with self.assertNumQueries(7):
            self.client.get("/modern-urun-ara/")


class StokYedekTesti(TestCase):
    """Stok urunlerini disa aktar, sil, geri yukle."""

    def setUp(self):
        self.yedek = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.yedek, True)

        self.kirtasiye = Liste_Grup.objects.create(Grup_Adi="Kırtasiye")
        Liste_Grup.objects.create(Grup_Adi="Boş Grup")   # hiç ürünü yok
        self.kalemler = UrunGruplari.objects.create(Grup_Adi="Kalemler")
        self.kagit = UrunGruplari.objects.create(Grup_Adi="Kağıt Ürünleri")

        u = Stok.objects.create(
            Urun_Adi="A4 Fotokopi Kağıdı", Barkod=8690000000001,
            Tutar=185, Liste_grup=self.kirtasiye, Favori=True,
        )
        u.Grup.set([self.kagit, self.kalemler])
        Stok.objects.create(Urun_Adi="Silgi", Barkod=8690000000002, Tutar=12)

    def _disa_aktar(self):
        call_command("stok_disa_aktar", klasor=self.yedek, verbosity=0)
        return Path(self.yedek) / "urunler.csv"

    def _her_seyi_sil(self):
        Stok.objects.all().delete()
        Liste_Grup.objects.all().delete()
        UrunGruplari.objects.all().delete()

    def test_yedek_dosyalari_olusur(self):
        self._disa_aktar()
        klasor = Path(self.yedek)

        for ad in ("urunler.csv", "liste-gruplari.csv", "urun-gruplari.csv", "tum-veri.json"):
            with self.subTest(dosya=ad):
                self.assertTrue((klasor / ad).is_file())

    def test_urunler_geri_yuklenir(self):
        csv_yolu = self._disa_aktar()
        self._her_seyi_sil()

        call_command("stok_ice_aktar", str(csv_yolu), "--uygula", verbosity=0)

        self.assertEqual(Stok.objects.count(), 2)
        u = Stok.objects.get(Barkod=8690000000001)
        self.assertEqual(u.Urun_Adi, "A4 Fotokopi Kağıdı")
        self.assertEqual(u.Tutar, 185)
        self.assertTrue(u.Favori)
        self.assertEqual(u.Liste_grup.Grup_Adi, "Kırtasiye")
        self.assertEqual(
            {g.Grup_Adi for g in u.Grup.all()}, {"Kağıt Ürünleri", "Kalemler"}
        )

    def test_arama_alani_geri_yuklemede_dolar(self):
        """Stok.save() Urun_Genel'i hesaplar; toplu ekleme kullanilsaydi arama bozulurdu."""
        csv_yolu = self._disa_aktar()
        self._her_seyi_sil()

        call_command("stok_ice_aktar", str(csv_yolu), "--uygula", verbosity=0)

        self.assertEqual(Stok.objects.filter(Urun_Genel__icontains="Fotokopi").count(), 1)
        self.assertEqual(Stok.objects.filter(Urun_Genel__icontains="8690000000002").count(), 1)

    def test_urunu_olmayan_grup_da_geri_gelir(self):
        csv_yolu = self._disa_aktar()
        self._her_seyi_sil()

        call_command("stok_ice_aktar", str(csv_yolu), "--uygula", verbosity=0)

        self.assertTrue(Liste_Grup.objects.filter(Grup_Adi="Boş Grup").exists())
        self.assertEqual(Liste_Grup.objects.count(), 2)

    def test_kuru_calisma_veriyi_degistirmez(self):
        csv_yolu = self._disa_aktar()
        self._her_seyi_sil()

        call_command("stok_ice_aktar", str(csv_yolu), verbosity=0)

        self.assertEqual(Stok.objects.count(), 0)

    def test_mevcut_urun_barkoda_gore_guncellenir(self):
        """Excel'de fiyat degistirip geri yuklemek: kopya urun olusmamali."""
        csv_yolu = self._disa_aktar()
        csv_yolu.write_text(
            csv_yolu.read_text(encoding="utf-8-sig").replace(",185.00,", ",210.00,"),
            encoding="utf-8-sig",
        )

        call_command("stok_ice_aktar", str(csv_yolu), "--uygula", verbosity=0)

        self.assertEqual(Stok.objects.count(), 2, "kopya ürün oluşmamalı")
        self.assertEqual(Stok.objects.get(Barkod=8690000000001).Tutar, 210)

    def test_bozuk_satirlar_atlanir(self):
        csv_yolu = self._disa_aktar()
        with csv_yolu.open("a", encoding="utf-8-sig") as dosya:
            dosya.write("barkod-degil,Bozuk Urun,50,,,hayir,evet,hayir\n")
            dosya.write("8690000000009,Fiyati Bozuk,fiyat,,,hayir,evet,hayir\n")
        self._her_seyi_sil()

        call_command("stok_ice_aktar", str(csv_yolu), "--uygula", verbosity=0)

        self.assertEqual(Stok.objects.count(), 2, "sadece geçerli satırlar yüklenmeli")
        self.assertFalse(Stok.objects.filter(Urun_Adi="Bozuk Urun").exists())
