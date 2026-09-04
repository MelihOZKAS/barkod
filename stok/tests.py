"""Sepet miktar guncelleme testleri.

Bu uc nokta canli kasada kullaniliyor: miktar alani <select> iken gecersiz
deger gelmesi imkansizdi, <input type=number> olunca mumkun hale geldi.
Testler o sinirlari koruyor.

Calistirmak icin:
    python manage.py test stok
"""

from datetime import date
from decimal import Decimal
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from kahve.models import KahveSatis

from . import barkod
from . import etiket as etiket_modulu
from . import rapor
from .models import (BorcHareketi, Liste_Grup, Musteri, Satis, SatisSatiri,
                     SepetUrun, Stok, StokHareketi, UrunGruplari)


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


class AdminCsvIndirmeTesti(TestCase):
    """Admin'deki 'CSV olarak indir' eylemi."""

    def setUp(self):
        User.objects.create_superuser("yonetici", "y@o.com", "gizli-sifre-123")
        self.client.login(username="yonetici", password="gizli-sifre-123")

        self.grup = Liste_Grup.objects.create(Grup_Adi="Kırtasiye")
        self.kagit = UrunGruplari.objects.create(Grup_Adi="Kağıt Ürünleri")
        u = Stok.objects.create(
            Urun_Adi="A4 Fotokopi Kağıdı", Barkod=8690000000001,
            Tutar=185, Liste_grup=self.grup, Favori=True,
        )
        u.Grup.set([self.kagit])
        Stok.objects.create(Urun_Adi="Silgi", Barkod=8690000000002, Tutar=12)

    def _indir(self):
        return self.client.post(
            "/admin/stok/stok/",
            {
                "action": "csv_indir",
                "_selected_action": list(Stok.objects.values_list("pk", flat=True)),
            },
        )

    def test_csv_dosyasi_iner(self):
        cevap = self._indir()

        self.assertEqual(cevap.status_code, 200)
        self.assertIn("text/csv", cevap["Content-Type"])
        self.assertIn("attachment", cevap["Content-Disposition"])

    def test_sadece_bir_bom_olur(self):
        """charset=utf-8-sig verilirse Django her write()'ta BOM ekler ve
        dosya geri yuklenemez hale gelir. Bir kere olmali."""
        govde = self._indir().content.decode("utf-8")

        self.assertEqual(govde.count("\ufeff"), 1)
        self.assertTrue(govde.startswith("\ufeffbarkod,"))

    def test_inen_dosya_geri_yuklenebilir(self):
        icerik = self._indir().content.decode("utf-8")
        klasor = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, klasor, True)
        yol = Path(klasor) / "yedek.csv"
        yol.write_text(icerik, encoding="utf-8")

        Stok.objects.all().delete()
        Liste_Grup.objects.all().delete()
        UrunGruplari.objects.all().delete()

        call_command("stok_ice_aktar", str(yol), "--uygula", verbosity=0)

        self.assertEqual(Stok.objects.count(), 2)
        u = Stok.objects.get(Barkod=8690000000001)
        self.assertEqual(u.Tutar, 185)
        self.assertEqual(u.Liste_grup.Grup_Adi, "Kırtasiye")
        self.assertEqual({g.Grup_Adi for g in u.Grup.all()}, {"Kağıt Ürünleri"})
        self.assertEqual(Stok.objects.filter(Urun_Genel__icontains="Fotokopi").count(), 1)

    def test_gruplar_da_indirilebilir(self):
        cevap = self.client.post(
            "/admin/stok/liste_grup/",
            {"action": "csv_indir", "_selected_action": [self.grup.pk]},
        )

        self.assertEqual(cevap.status_code, 200)
        govde = cevap.content.decode("utf-8")
        self.assertEqual(govde.count("\ufeff"), 1)
        self.assertIn("Kırtasiye", govde)


class SatisKaydiTesti(TestCase):
    """Satisi tamamlama: kayit, stok dusumu, borc.

    Onceden sepet sadece siliniyordu; hicbir yere ne satildigi yazilmiyordu.
    """

    def setUp(self):
        self.kullanici = User.objects.create_user("kasiyer", password="gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")
        # takip edilen urun (adedi girilmis) ve edilmeyen (adedi bos)
        self.takipli = Stok.objects.create(Urun_Adi="Defter", Barkod=1001,
                                           Tutar=Decimal("50.00"), stok_adedi=10)
        self.takipsiz = Stok.objects.create(Urun_Adi="Silgi", Barkod=1002,
                                            Tutar=Decimal("10.00"))
        self.musteri = Musteri.objects.create(isim_soyisim="Veresiye Müşteri",
                                              Cep_Telefonu=5551112233, borc=Decimal("0.00"))

    def _sepete(self, urun, miktar=1):
        SepetUrun.objects.create(user=self.kullanici, urun=urun, miktar=miktar)

    def test_nakit_satis_kaydedilir_ve_sepet_temizlenir(self):
        self._sepete(self.takipli, 2)

        cevap = self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        self.assertTrue(cevap.json()["success"])
        satis = Satis.objects.get()
        self.assertEqual(satis.toplam, Decimal("100.00"))
        self.assertEqual(satis.nakit_tutar, Decimal("100.00"))
        self.assertEqual(satis.kart_tutar, Decimal("0.00"))
        self.assertEqual(satis.satirlar.count(), 1)
        self.assertEqual(SepetUrun.objects.count(), 0, "sepet temizlenmeli")

    def test_satirlar_o_anki_fiyati_saklar(self):
        """Sonradan zam yapilsa da gecmis satis bozulmamali."""
        self._sepete(self.takipli, 1)
        self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        self.takipli.Tutar = Decimal("80.00")
        self.takipli.save()

        satir = SatisSatiri.objects.get()
        self.assertEqual(satir.birim_fiyat, Decimal("50.00"))
        self.assertEqual(satir.urun_adi, "Defter")

    def test_adedi_girilmis_urunun_stogu_duser(self):
        self._sepete(self.takipli, 3)

        self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "kart"})

        self.takipli.refresh_from_db()
        self.assertEqual(self.takipli.stok_adedi, 7)
        hareket = StokHareketi.objects.get(urun=self.takipli)
        self.assertEqual(hareket.miktar, -3)
        self.assertEqual(hareket.onceki_adet, 10)
        self.assertEqual(hareket.sonraki_adet, 7)
        self.assertEqual(hareket.tur, StokHareketi.Tur.SATIS)

    def test_adedi_bos_urun_takip_edilmez(self):
        """Binlerce urunun sayimi yok; adedi bos olan urune dokunulmamali."""
        self._sepete(self.takipsiz, 5)

        self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        self.takipsiz.refresh_from_db()
        self.assertIsNone(self.takipsiz.stok_adedi)
        self.assertEqual(StokHareketi.objects.count(), 0)

    def test_parcali_tutarlar_tutmuyorsa_reddedilir(self):
        self._sepete(self.takipli, 2)   # 100 TL

        cevap = self.client.post(reverse("api-satis-tamamla"),
                                 {"odeme_turu": "parcali", "nakit": "40", "kart": "30"})

        self.assertFalse(cevap.json()["success"])
        self.assertEqual(Satis.objects.count(), 0, "hatali satis kaydedilmemeli")
        self.assertEqual(SepetUrun.objects.count(), 1, "sepet durmali")

    def test_bos_sepet_satilamaz(self):
        cevap = self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        self.assertFalse(cevap.json()["success"])
        self.assertEqual(Satis.objects.count(), 0)

    def test_anonim_satis_yapamaz(self):
        anonim = Client()

        cevap = anonim.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        self.assertEqual(cevap.status_code, 302)


class BorcaAktarmaTesti(TestCase):
    """Borca aktarma: borc hanesi, aciklama ve satis kaydi birlikte."""

    def setUp(self):
        self.kullanici = User.objects.create_user("kasiyer", password="gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")
        self.urun = Stok.objects.create(Urun_Adi="Defter", Barkod=2001, Tutar=Decimal("50.00"))
        self.kalem = Stok.objects.create(Urun_Adi="Kalem", Barkod=2002, Tutar=Decimal("20.00"))
        self.musteri = Musteri.objects.create(isim_soyisim="Veresiye Müşteri",
                                              Cep_Telefonu=5551112233, borc=Decimal("30.00"))
        SepetUrun.objects.create(user=self.kullanici, urun=self.urun, miktar=2)
        SepetUrun.objects.create(user=self.kullanici, urun=self.kalem, miktar=1)

    def test_tumu_borca_yazilir(self):
        cevap = self.client.post(reverse("api-borca-aktar"),
                                 {"musteri_id": self.musteri.id, "tutar": "120"})

        self.assertTrue(cevap.json()["success"])
        self.musteri.refresh_from_db()
        self.assertEqual(self.musteri.borc, Decimal("150.00"), "30 + 120")

    def test_aciklama_alinanlari_ve_notu_yazar(self):
        self.client.post(reverse("api-borca-aktar"), {
            "musteri_id": self.musteri.id, "tutar": "120", "not": "cumartesi ödeyecek",
        })

        hareket = BorcHareketi.objects.get()
        self.assertIn("2x Defter", hareket.aciklama)
        self.assertIn("1x Kalem", hareket.aciklama)
        self.assertIn("cumartesi ödeyecek", hareket.aciklama)
        self.assertEqual(hareket.onceki_borc, Decimal("30.00"))

    def test_parcali_aktarmada_kalan_kasaya_yazilir(self):
        self.client.post(reverse("api-borca-aktar"),
                         {"musteri_id": self.musteri.id, "tutar": "50"})

        satis = Satis.objects.get()
        self.assertEqual(satis.toplam, Decimal("120.00"))
        self.assertEqual(satis.borc_tutar, Decimal("50.00"))
        self.assertEqual(satis.nakit_tutar, Decimal("70.00"), "kalan kasaya nakit")
        self.musteri.refresh_from_db()
        self.assertEqual(self.musteri.borc, Decimal("80.00"), "30 + 50")
        self.assertIn("Parçalı", BorcHareketi.objects.get().aciklama)

    def test_sepetten_buyuk_tutar_reddedilir(self):
        cevap = self.client.post(reverse("api-borca-aktar"),
                                 {"musteri_id": self.musteri.id, "tutar": "500"})

        self.assertFalse(cevap.json()["success"])
        self.musteri.refresh_from_db()
        self.assertEqual(self.musteri.borc, Decimal("30.00"), "borç değişmemeli")
        self.assertEqual(Satis.objects.count(), 0)

    def test_borca_aktarma_satis_kaydi_da_uretir(self):
        """Kasa raporu ancak boyle 'ne kadari borca yazildi' diyebiliyor."""
        self.client.post(reverse("api-borca-aktar"),
                         {"musteri_id": self.musteri.id, "tutar": "120"})

        satis = Satis.objects.get()
        self.assertEqual(satis.odeme_turu, Satis.Odeme.BORC)
        self.assertEqual(satis.borc_musteri, self.musteri)
        self.assertEqual(satis.satirlar.count(), 2)


class KasaRaporuTesti(TestCase):
    """Iki tezgahin parasi tek raporda."""

    def setUp(self):
        User.objects.create_user("kasiyer", password="gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")
        self.musteri = Musteri.objects.create(isim_soyisim="Veresiye",
                                              Cep_Telefonu=5551112233, borc=0)
        Satis.objects.create(toplam=Decimal("100"), nakit_tutar=Decimal("100"),
                             odeme_turu=Satis.Odeme.NAKIT)
        Satis.objects.create(toplam=Decimal("60"), kart_tutar=Decimal("60"),
                             odeme_turu=Satis.Odeme.KART)
        Satis.objects.create(toplam=Decimal("40"), borc_tutar=Decimal("40"),
                             odeme_turu=Satis.Odeme.BORC, borc_musteri=self.musteri)
        KahveSatis.objects.create(toplam=Decimal("80"), nakit_tutar=Decimal("80"),
                                  odeme_turu=KahveSatis.Odeme.NAKIT)

    def test_gunluk_ozet_iki_tezgahi_toplar(self):
        bugun = timezone.localtime().date()

        ozet = rapor.ozet(bugun, bugun)

        self.assertEqual(ozet["toplam"]["ciro"], Decimal("280"))
        self.assertEqual(ozet["toplam"]["nakit"], Decimal("180"))
        self.assertEqual(ozet["toplam"]["kart"], Decimal("60"))
        self.assertEqual(ozet["toplam"]["borc"], Decimal("40"))
        self.assertEqual(ozet["kirtasiye"]["ciro"], Decimal("200"))
        self.assertEqual(ozet["kahve"]["ciro"], Decimal("80"))

    def test_borc_kasaya_para_olarak_girmez(self):
        bugun = timezone.localtime().date()

        ozet = rapor.ozet(bugun, bugun)

        kasaya = ozet["toplam"]["nakit"] + ozet["toplam"]["kart"]
        self.assertEqual(kasaya, Decimal("240"))
        self.assertEqual(ozet["toplam"]["ciro"] - kasaya, ozet["toplam"]["borc"])

    def test_tezgah_dokumu_ayri_ayri_gosterilir(self):
        """Iki tezgah ayri isliyor; nakit/kart/borc kirilimi de ayri gorunmeli."""
        cevap = self.client.get(reverse("kasa-raporu"), {"donem": "gun"})
        govde = cevap.content.decode()

        self.assertContains(cevap, "Tezgâh dökümü")
        # kirtasiye 100 nakit + 60 kart, kahve 80 nakit
        for beklenen in ("Kırtasiye", "Kahve", "Borca yazılan", "Satış adedi"):
            with self.subTest(beklenen=beklenen):
                self.assertIn(beklenen, govde)

    def test_rapor_sayfasi_acilir(self):
        for donem in ("gun", "ay", "yil"):
            with self.subTest(donem=donem):
                cevap = self.client.get(reverse("kasa-raporu"), {"donem": donem})

                self.assertEqual(cevap.status_code, 200)
                self.assertContains(cevap, "Toplam ciro")

    def test_anonim_rapor_goremez(self):
        anonim = Client()

        self.assertEqual(anonim.get(reverse("kasa-raporu")).status_code, 302)

    def test_kritik_stok_sadece_adedi_girilmisleri_listeler(self):
        Stok.objects.create(Urun_Adi="Azalan", Barkod=3001, Tutar=1, stok_adedi=2)
        Stok.objects.create(Urun_Adi="Bol", Barkod=3002, Tutar=1, stok_adedi=99)
        Stok.objects.create(Urun_Adi="Takipsiz", Barkod=3003, Tutar=1)

        adlar = [u.Urun_Adi for u in rapor.kritik_stok()]

        self.assertEqual(adlar, ["Azalan"])


class ParaUclariCsrfTesti(TestCase):
    """Para hareketi yazan uclar CSRF token'i olmadan calismamali.

    Bu iki uc satis kapatiyor, stok dusuyor ve musteriye borc yaziyor.
    Muafiyet birakilsaydi kotu niyetli bir sayfa, giris yapmis personelin
    tarayicisindan sessizce satis kapatabilirdi.
    """

    UCLAR = ("api-satis-tamamla", "api-borca-aktar")

    def setUp(self):
        self.kullanici = User.objects.create_user("kasiyer", password="gizli-sifre-123")
        self.urun = Stok.objects.create(Urun_Adi="Defter", Barkod=4001, Tutar=Decimal("50.00"))
        self.musteri = Musteri.objects.create(isim_soyisim="Veresiye",
                                              Cep_Telefonu=5551112233, borc=Decimal("0.00"))

    def test_tokensiz_istek_reddedilir(self):
        istemci = Client(enforce_csrf_checks=True)
        istemci.force_login(self.kullanici)
        SepetUrun.objects.create(user=self.kullanici, urun=self.urun, miktar=1)

        for uc in self.UCLAR:
            with self.subTest(uc=uc):
                cevap = istemci.post(reverse(uc),
                                     {"odeme_turu": "nakit", "musteri_id": self.musteri.id,
                                      "tutar": "50"})

                self.assertEqual(cevap.status_code, 403)

        self.assertEqual(Satis.objects.count(), 0, "hicbir satis yazilmamali")
        self.assertEqual(Musteri.objects.get(pk=self.musteri.pk).borc, Decimal("0.00"))

    def test_tokenli_istek_calisir(self):
        istemci = Client(enforce_csrf_checks=True)
        istemci.force_login(self.kullanici)
        istemci.get(reverse("modern-urun-ara"))          # csrftoken cerezi bu istekte kurulur
        token = istemci.cookies["csrftoken"].value
        SepetUrun.objects.create(user=self.kullanici, urun=self.urun, miktar=1)

        cevap = istemci.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"},
                             HTTP_X_CSRFTOKEN=token)

        self.assertEqual(cevap.status_code, 200)
        self.assertTrue(cevap.json()["success"])
        self.assertEqual(Satis.objects.count(), 1)

    def test_sayfa_token_i_js_e_veriyor(self):
        """Muafiyet kalkti; sayfanin token'i gonderebiliyor olmasi sart."""
        istemci = Client()
        istemci.force_login(self.kullanici)

        govde = istemci.get(reverse("modern-urun-ara")).content.decode()

        self.assertIn("csrfmiddlewaretoken", govde)
        self.assertIn("X-CSRFToken", govde)


class BakiyeEkranlariTesti(TestCase):
    """Iki ekran da SADECE POST'a cevap veriyordu.

    GET ile acilinca view None donuyor, Django "didn't return an HttpResponse"
    diye 500 veriyordu — musteri listesindeki "Hareketler" baglantisi normal
    bir link (GET) oldugu icin canlida patladi. Ustelik ikisinde de
    login_required yoktu: id tahmin eden herkes musterinin borcunu gorebiliyordu.
    """

    def setUp(self):
        self.kullanici = User.objects.create_user("kasiyer", password="gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")
        self.musteri = Musteri.objects.create(isim_soyisim="Ahmet Yılmaz",
                                              Cep_Telefonu=5551112233, borc=Decimal("240.00"))
        BorcHareketi.objects.create(
            musteri=self.musteri, tutar=Decimal("120.00"), onceki_borc=Decimal("120.00"),
            aciklama="Sepetten borça aktarıldı.\nAlınanlar: 2x Defter\nNot: cumartesi",
        )

    def test_iki_url_de_ayni_sayfayi_acar(self):
        """Eskiden iki ayri ekrandi; artik ikisi de borc detay sayfasi."""
        sayfalar = []
        for ad in ("bakiye", "bakiye-hareketi"):
            cevap = self.client.get(reverse(ad, args=[self.musteri.id]))
            self.assertEqual(cevap.status_code, 200)
            self.assertTemplateUsed(cevap, "system/user/musteri_borc.html")
            sayfalar.append(cevap.status_code)

        self.assertEqual(len(set(sayfalar)), 1)

    def test_hareket_yonu_ve_bakiye_gosterilir(self):
        BorcHareketi.objects.create(
            musteri=self.musteri, tutar=Decimal("40.00"),
            onceki_borc=Decimal("240.00"), aciklama="Borç düştü - nakit tahsilat",
        )

        govde = self.client.get(
            reverse("bakiye", args=[self.musteri.id])).content.decode()

        self.assertIn("−40,00 ₺", govde, "düşen borç eksi işaretiyle gösterilmeli")
        self.assertIn("240 → 200 ₺", govde, "işlem sonrası bakiye yazmalı")

    def test_get_ile_acilir(self):
        for ad in ("bakiye", "bakiye-hareketi"):
            with self.subTest(ad=ad):
                cevap = self.client.get(reverse(ad, args=[self.musteri.id]))

                self.assertEqual(cevap.status_code, 200)

    def test_hareket_sayfasi_musteriyi_ve_hareketi_gosterir(self):
        cevap = self.client.get(reverse("bakiye-hareketi", args=[self.musteri.id]))

        self.assertContains(cevap, "Ahmet Yılmaz")
        self.assertContains(cevap, "240")
        self.assertContains(cevap, "2x Defter")

    def test_cok_satirli_aciklama_ezilmiyor(self):
        """Borç açıklaması artık çok satırlı; tek satıra ezilmemeli.

        Sayfa bunu <br> uretmek yerine white-space:pre-line ile cozuyor;
        satir sonlari metnin icinde oldugu gibi duruyor.
        """
        govde = self.client.get(
            reverse("bakiye-hareketi", args=[self.musteri.id])).content.decode()

        self.assertIn("Alınanlar: 2x Defter\nNot: cumartesi", govde)
        self.assertIn("white-space:pre-line", govde.replace(" ", ""))

    def test_anonim_musterinin_borcunu_goremez(self):
        anonim = Client()

        for ad in ("bakiye", "bakiye-hareketi"):
            with self.subTest(ad=ad):
                cevap = anonim.get(reverse(ad, args=[self.musteri.id]))

                self.assertEqual(cevap.status_code, 302)
                self.assertNotIn("Ahmet", cevap.content.decode())

    def test_olmayan_musteri_500_degil_404(self):
        cevap = self.client.get(reverse("bakiye-hareketi", args=[999999]))

        self.assertEqual(cevap.status_code, 404)


class KorumasizUcTesti(TestCase):
    """Veri degistiren hicbir uc anonim istekle calismamali.

    Tarama sonucu: borc_duzenle musterinin borcunu degistiriyordu,
    stok_sil urun siliyordu ve ikisinde de login_required yoktu; ustelik
    csrf_exempt olduklari icin disaridan duz bir POST yeterliydi.
    """

    # (url adi, gerekirse argumanlar)
    UCLAR = [
        ("borc-duzenle", [1]),
        ("stok_sil", []),
        ("oto-ekle", []),
        ("oto-grupla", []),
        ("musteri-ekle", []),
        ("manuel-tutar", []),
        ("sepeti-sifirla", []),
        ("modern-sepeti-sifirla", []),
    ]

    def test_anonim_hicbirine_erisemez(self):
        anonim = Client()

        for ad, argumanlar in self.UCLAR:
            with self.subTest(uc=ad):
                adres = reverse(ad, args=argumanlar)

                self.assertEqual(anonim.get(adres).status_code, 302)
                self.assertEqual(anonim.post(adres, {}).status_code, 302)

    def test_anonim_borcu_degistiremez(self):
        musteri = Musteri.objects.create(isim_soyisim="Kurban",
                                         Cep_Telefonu=5551112233, borc=Decimal("100.00"))
        anonim = Client()

        anonim.post(reverse("borc-duzenle", args=[musteri.id]),
                    {"tutar": "9999", "aciklama": "saldiri", "islem": "borcekle"})

        musteri.refresh_from_db()
        self.assertEqual(musteri.borc, Decimal("100.00"), "borç değişmemeli")
        self.assertEqual(BorcHareketi.objects.count(), 0)

    def test_anonim_urun_silemez(self):
        Stok.objects.create(Urun_Adi="Silinmesin", Barkod=7001, Tutar=Decimal("10"))
        anonim = Client()

        anonim.post(reverse("stok_sil"), {})

        self.assertEqual(Stok.objects.count(), 1)

    def test_get_ile_acilinca_500_vermez(self):
        """Bu view'lar sadece POST'a cevap veriyor, GET'te None donuyorlardi."""
        kullanici = User.objects.create_user("kasiyer", password="gizli-sifre-123")
        musteri = Musteri.objects.create(isim_soyisim="Ahmet",
                                         Cep_Telefonu=5551112233, borc=Decimal("0"))
        istemci = Client()
        istemci.force_login(kullanici)

        for ad, argumanlar in (("borc-duzenle", [musteri.id]), ("manuel-tutar", [])):
            with self.subTest(uc=ad):
                cevap = istemci.get(reverse(ad, args=argumanlar))

                self.assertIn(cevap.status_code, (200, 302), "500 olmamali")


class SepettekiStokGostergesiTesti(TestCase):
    """Kasada adet alaninin altinda urunun kalan stogu yazsin."""

    def setUp(self):
        self.kullanici = User.objects.create_user("kasiyer", password="gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")

    def _sepete(self, urun, miktar=1):
        SepetUrun.objects.create(user=self.kullanici, urun=urun, miktar=miktar)
        return self.client.get(reverse("modern-urun-ara")).content.decode()

    def test_adedi_girilmis_urunun_stogu_yazar(self):
        urun = Stok.objects.create(Urun_Adi="Defter", Barkod=9001,
                                   Tutar=Decimal("80"), stok_adedi=16)

        govde = self._sepete(urun)

        self.assertIn("Stok: 16", govde)

    def test_adedi_bos_urun_icin_hicbir_sey_yazmaz(self):
        """Takip edilmeyen urune yanlis bir '0' yazmaktansa sessiz kal."""
        urun = Stok.objects.create(Urun_Adi="Silgi", Barkod=9002, Tutar=Decimal("10"))

        govde = self._sepete(urun)

        self.assertNotIn("Stok:", govde)
        self.assertNotIn("Stokta yok", govde)

    def test_stok_sepetteki_adetten_azsa_uyarir(self):
        urun = Stok.objects.create(Urun_Adi="Kalem", Barkod=9003,
                                   Tutar=Decimal("20"), stok_adedi=2)

        govde = self._sepete(urun, miktar=5)

        self.assertIn("yetersiz", govde)
        self.assertIn("Stok: 2", govde)

    def test_stok_bitmisse_ayri_yazar(self):
        urun = Stok.objects.create(Urun_Adi="Cetvel", Barkod=9004,
                                   Tutar=Decimal("30"), stok_adedi=0)

        govde = self._sepete(urun)

        self.assertIn("Stokta yok", govde)


class OzelIndirimTesti(TestCase):
    """Kasada elle verilen indirim: TL ya da yuzde.

    Indirim satisin her yerine dokunuyor - kayit, borc ve kasa raporu.
    """

    def setUp(self):
        self.kullanici = User.objects.create_user("kasiyer", password="gizli-sifre-123")
        self.client = Client()
        self.client.login(username="kasiyer", password="gizli-sifre-123")
        self.urun = Stok.objects.create(Urun_Adi="Defter", Barkod=6001, Tutar=Decimal("50.00"))
        SepetUrun.objects.create(user=self.kullanici, urun=self.urun, miktar=4)   # 200 TL
        self.musteri = Musteri.objects.create(isim_soyisim="Veresiye",
                                              Cep_Telefonu=5551112233, borc=Decimal("0"))

    def _indirim(self, tur, deger):
        return self.client.post(reverse("api-indirim-uygula"), {"tur": tur, "deger": deger})

    def test_tl_indirimi_toplamdan_duser(self):
        cevap = self._indirim("tl", "30")

        veri = cevap.json()["indirim"]
        self.assertEqual(veri["ara_toplam"], "200.00")
        self.assertEqual(veri["tutar"], "30.00")
        self.assertEqual(veri["odenecek"], "170.00")

    def test_yuzde_indirimi_hesaplanir(self):
        veri = self._indirim("yuzde", "10").json()["indirim"]

        self.assertEqual(veri["tutar"], "20.00")
        self.assertEqual(veri["odenecek"], "180.00")

    def test_satis_indirimli_tutarla_kaydedilir(self):
        self._indirim("tl", "30")

        self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        satis = Satis.objects.get()
        self.assertEqual(satis.indirim_tutari, Decimal("30.00"))
        self.assertEqual(satis.toplam, Decimal("170.00"), "kasaya giren indirimli tutar")
        self.assertEqual(satis.nakit_tutar, Decimal("170.00"))
        self.assertEqual(satis.ara_toplam, Decimal("200.00"))

    def test_satis_bitince_indirim_temizlenir(self):
        """Yarim kalan indirim bir sonraki musteriye tasinmamali."""
        self._indirim("tl", "30")
        self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        SepetUrun.objects.create(user=self.kullanici, urun=self.urun, miktar=1)
        self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        ikinci = Satis.objects.order_by("id").last()
        self.assertEqual(ikinci.indirim_tutari, Decimal("0.00"))
        self.assertEqual(ikinci.toplam, Decimal("50.00"))

    def test_borca_aktarmada_da_indirim_gecerli(self):
        self._indirim("yuzde", "25")     # 200 -> 150

        self.client.post(reverse("api-borca-aktar"),
                         {"musteri_id": self.musteri.id, "tutar": "150"})

        self.musteri.refresh_from_db()
        self.assertEqual(self.musteri.borc, Decimal("150.00"))
        satis = Satis.objects.get()
        self.assertEqual(satis.indirim_tutari, Decimal("50.00"))
        self.assertIn("İndirim", BorcHareketi.objects.get().aciklama)

    def test_sepetten_buyuk_indirim_kabul_edilmez(self):
        """Toplami asan indirim eksi tutar uretmemeli."""
        self._indirim("tl", "500")

        self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})

        satis = Satis.objects.get()
        self.assertEqual(satis.toplam, Decimal("0.00"), "eksiye düşmemeli")
        self.assertEqual(satis.indirim_tutari, Decimal("200.00"), "en fazla ara toplam kadar")

    def test_yuzde_yuzden_buyuk_olamaz(self):
        cevap = self._indirim("yuzde", "150")

        self.assertFalse(cevap.json()["success"])

    def test_eksi_indirim_reddedilir(self):
        cevap = self._indirim("tl", "-50")

        self.assertFalse(cevap.json()["success"])

    def test_sifir_indirim_kaldirir(self):
        self._indirim("tl", "30")

        veri = self._indirim("tl", "0").json()["indirim"]

        self.assertFalse(veri["var"])
        self.assertEqual(veri["odenecek"], "200.00")

    def test_raporda_ciro_indirimli_tutar(self):
        self._indirim("tl", "30")
        self.client.post(reverse("api-satis-tamamla"), {"odeme_turu": "nakit"})
        bugun = timezone.localtime().date()

        ozet = rapor.ozet(bugun, bugun)

        self.assertEqual(ozet["toplam"]["ciro"], Decimal("170.00"))

    def test_kasa_sayfasi_indirimi_gosterir(self):
        """Uc dogru cevap verse de sayfa gostermezse ise yaramaz.

        Ilk yazimda context iki render yolundan sadece birine eklenmisti;
        duz GET'te GENEL TOPLAM bos cikiyordu.
        """
        self._indirim("tl", "30")

        cevap = self.client.get(reverse("modern-urun-ara"))
        govde = cevap.content.decode()

        self.assertIn("Özel indirim", govde)
        # Site Turkce yerellestirmede: ondalik ayrac virgul
        self.assertIn("170,00 TL", govde, "genel toplam indirimli olmalı")
        self.assertIn("30,00 TL", govde, "indirim tutarı görünmeli")
        self.assertIn('id="indirim-kaldir"', govde, "kaldır düğmesi çıkmalı")

    def test_js_e_giden_tutar_noktali(self):
        """parseFloat virgullu sayida kurusu yutuyor; JS'e nokta gitmeli."""
        self._indirim("tl", "30.50")

        govde = self.client.get(reverse("modern-urun-ara")).content.decode()

        self.assertIn("var sepetToplam = '169.50'", govde)

    def test_indirim_yokken_toplam_bozulmaz(self):
        govde = self.client.get(reverse("modern-urun-ara")).content.decode()

        self.assertIn("200,00 TL", govde)
        self.assertNotIn('id="indirim-kaldir"', govde)

    def test_anonim_indirim_veremez(self):
        anonim = Client()

        self.assertEqual(anonim.post(reverse("api-indirim-uygula"),
                                     {"tur": "tl", "deger": "50"}).status_code, 302)


class BarkodCizimiTesti(TestCase):
    """stok/barkod.py -- disaridan paket kurmadan cizilen barkod.

    Yanlis cizilmis bir barkod ekranda dogru gorunur ama okuyucu okumaz; hata
    ancak raf etiketleri basildiktan sonra fark edilir. Testler kod tablolarini
    ve kontrol hanesini kilitliyor.
    """

    def test_kod_tablolari_tutarli(self):
        """SAG = SOL_TEK'in tersi, SOL_CIFT = SAG'in ters cevrilmisi.

        Tablolara elle dokunulup bir hane yanlis yazilirsa buradan yakalanir.
        """
        for hane in range(10):
            self.assertEqual(
                barkod.SAG[hane],
                barkod.SOL_TEK[hane].translate(str.maketrans("01", "10")),
                f"{hane} icin sag kod sol kodun tersi olmali",
            )
            self.assertEqual(barkod.SOL_CIFT[hane], barkod.SAG[hane][::-1])

    def test_ean13_kontrol_hanesi(self):
        self.assertEqual(barkod.ean_kontrol_hanesi("868067980102"), 7)
        self.assertEqual(barkod.ean_kontrol_hanesi("590123412345"), 7)

    def test_ean8_kontrol_hanesi(self):
        self.assertEqual(barkod.ean_kontrol_hanesi("9638507"), 4)

    def test_gecerli_ean13_ean13_cizilir(self):
        cizim = barkod.barkod_ciz(8680679801027)

        self.assertEqual(cizim.tur, "EAN-13")
        self.assertEqual(cizim.metin, "8680679801027")
        # 11 sessiz + 95 govde + 7 sessiz
        self.assertEqual(cizim.genislik, 113)
        govde = cizim.moduller[11:-7]
        self.assertTrue(govde.startswith("101"), "bas koruma cubugu")
        self.assertTrue(govde.endswith("101"), "son koruma cubugu")
        self.assertEqual(govde[45:50], "01010", "orta koruma cubugu")

    def test_kontrol_hanesi_tutmayan_sayi_ean_olarak_cizilmez(self):
        """Okuyucu gecersiz EAN'i hic okumaz; Code 128 ise sayiyi oldugu gibi
        tasir, yani okutuldugunda etiketteki rakamlarin ayni cikar."""
        cizim = barkod.barkod_ciz(8680679801020)

        self.assertEqual(cizim.tur, "Code 128")
        self.assertEqual(cizim.metin, "8680679801020")

    def test_gecerli_ean8_ean8_cizilir(self):
        cizim = barkod.barkod_ciz(96385074)

        self.assertEqual(cizim.tur, "EAN-8")
        self.assertEqual(cizim.genislik, 11 + 67 + 7)

    def test_kisa_dahili_barkod_code128_olur(self):
        cizim = barkod.barkod_ciz(1234)

        self.assertEqual(cizim.tur, "Code 128")
        self.assertEqual(cizim.metin, "1234")

    def test_code128_kontrol_toplami(self):
        """Start C (105) + 1*12 + 2*34 = 185; 185 % 103 = 82."""
        degerler = barkod.code128_degerleri("1234")

        self.assertEqual(degerler, [105, 12, 34, 82, 106])

    def test_code128_tek_sayida_hane(self):
        """Tek haneli kalinti C kumesinde kodlanamaz; cizim yine de uretilmeli."""
        cizim = barkod.barkod_ciz(12345)

        self.assertEqual(cizim.tur, "Code 128")
        self.assertTrue(cizim.moduller.strip("0"))

    def test_bos_deger_barkod_uretmez(self):
        self.assertIsNone(barkod.barkod_ciz(""))
        self.assertIsNone(barkod.barkod_ciz(None))

    def test_svg_olcek_bagimsiz(self):
        """viewBox modul sayisi kadar; etiket kucuk ya da buyuk olsun bar
        oranlari bozulmadan olceklensin."""
        svg = barkod.barkod_ciz(8680679801027).svg

        self.assertIn('viewBox="0 0 113 100"', svg)
        self.assertIn('fill="#000"', svg)
        self.assertIn("</svg>", svg)


class FiyatDegisimTarihiTesti(TestCase):
    """Etiketteki F.D.T. alani.

    guncelleme_tarihi bunun yerine gecemez: stok adedi degisince o da ilerliyor,
    etikette fiyat degismemis urun icin yanlis tarih basardi.
    """

    def setUp(self):
        self.bugun = timezone.localdate()
        self.urun = Stok.objects.create(Urun_Adi="Guaj Boya", Barkod=8680679801027, Tutar=110)

    def test_yeni_urun_bugunu_alir(self):
        self.assertEqual(self.urun.fiyat_tarihi, self.bugun)

    def test_fiyat_degisince_tarih_tazelenir(self):
        Stok.objects.filter(pk=self.urun.pk).update(fiyat_tarihi=date(2020, 1, 1))

        urun = Stok.objects.get(pk=self.urun.pk)
        urun.Tutar = Decimal("125.00")
        urun.save()

        self.assertEqual(urun.fiyat_tarihi, self.bugun)

    def test_fiyat_degismeyince_tarihe_dokunulmaz(self):
        eski = date(2020, 1, 1)
        Stok.objects.filter(pk=self.urun.pk).update(fiyat_tarihi=eski)

        urun = Stok.objects.get(pk=self.urun.pk)
        urun.Urun_Adi = "Guaj Boya 25 ml"
        urun.stok_adedi = 40
        urun.save()

        self.assertEqual(urun.fiyat_tarihi, eski)

    def test_satista_stok_dusunce_tarihe_dokunulmaz(self):
        """satis.py urunu save(update_fields=['stok_adedi']) ile kaydediyor."""
        eski = date(2020, 1, 1)
        Stok.objects.filter(pk=self.urun.pk).update(fiyat_tarihi=eski, stok_adedi=10)

        urun = Stok.objects.get(pk=self.urun.pk)
        urun.stok_adedi = 9
        urun.save(update_fields=["stok_adedi"])
        urun.refresh_from_db()

        self.assertEqual(urun.fiyat_tarihi, eski)

    def test_admin_zam_eylemi_tarihi_tazeler(self):
        Stok.objects.filter(pk=self.urun.pk).update(fiyat_tarihi=date(2020, 1, 1))
        User.objects.create_superuser("yonetici", "y@o.com", "gizli-sifre-123")
        self.client.login(username="yonetici", password="gizli-sifre-123")

        self.client.post("/admin/stok/stok/", {
            "action": "Yuzde10ZamYap",
            "_selected_action": [str(self.urun.pk)],
        })

        self.urun.refresh_from_db()
        self.assertEqual(self.urun.fiyat_tarihi, self.bugun)
        self.assertEqual(self.urun.Tutar, Decimal("122.00"))

    def test_elle_yazilan_tarih_korunur(self):
        urun = Stok.objects.create(
            Urun_Adi="Elle Tarihli", Barkod=8690000000777,
            Tutar=50, fiyat_tarihi=date(2024, 5, 6),
        )

        self.assertEqual(urun.fiyat_tarihi, date(2024, 5, 6))


class EtiketSayfasiTesti(TestCase):
    """/etiket/ -- raf etiketi cikti sayfasi."""

    def setUp(self):
        self.sifre = "kasa-sifresi-123"
        User.objects.create_user("kasa", password=self.sifre)
        self.client.login(username="kasa", password=self.sifre)

        self.urun = Stok.objects.create(
            Urun_Adi="Lets 6 Renk Guaj Boya 25ml", Barkod=8680679801027,
            Tutar=Decimal("110.00"), birim="AD", uretim_yeri="Türkiye",
        )
        self.ikinci = Stok.objects.create(
            Urun_Adi="Silgi", Barkod=8690000000002, Tutar=Decimal("12.50"))

    def _govde(self, **parametreler):
        cevap = self.client.get(reverse("etiket"), parametreler)
        self.assertEqual(cevap.status_code, 200)
        return cevap.content.decode()

    def test_anonim_giremez(self):
        anonim = Client()

        self.assertEqual(anonim.get(reverse("etiket")).status_code, 302)

    def test_etikette_yonetmeligin_istedigi_her_sey_var(self):
        govde = self._govde(ids=str(self.urun.pk))

        self.assertIn("Lets 6 Renk Guaj Boya 25ml", govde)
        self.assertIn("110,00", govde)          # tr yerellestirmesi: virgul
        self.assertIn("KDV Dahildir.", govde)
        self.assertIn("Birim: AD", govde)
        self.assertIn("Üretim Yeri: Türkiye", govde)
        self.assertIn(f"F.D.T: {timezone.localdate():%d.%m.%Y}", govde)
        self.assertIn("8680679801027", govde)
        self.assertIn('viewBox="0 0 113 100"', govde)

    def test_birimi_bos_urun_ad_yazar(self):
        Stok.objects.filter(pk=self.ikinci.pk).update(birim="")

        self.assertIn("Birim: AD", self._govde(ids=str(self.ikinci.pk)))

    def test_secim_sirasi_korunur(self):
        govde = self._govde(ids=f"{self.ikinci.pk},{self.urun.pk}")

        self.assertLess(govde.index("Silgi"), govde.index("Lets 6 Renk"))

    def test_oturumdaki_secim_okunur(self):
        oturum = self.client.session
        oturum[etiket_modulu.OTURUM_ANAHTARI] = [self.urun.pk]
        oturum.save()

        self.assertIn("Lets 6 Renk Guaj Boya 25ml", self._govde())

    def test_kopya_sayisi_kadar_basilir(self):
        govde = self._govde(ids=str(self.urun.pk), kopya="3")

        self.assertEqual(govde.count('<article class="etiket">'), 3)

    def test_kopya_sinirlari_zorlanamaz(self):
        for deger in ("0", "-5", "abc", "9999"):
            govde = self._govde(ids=str(self.urun.pk), kopya=deger)
            sayi = govde.count('<article class="etiket">')
            self.assertGreaterEqual(sayi, 1)
            self.assertLessEqual(sayi, etiket_modulu.EN_COK_KOPYA)

    def test_bilinmeyen_boyut_varsayilana_duser(self):
        govde = self._govde(ids=str(self.urun.pk), boyut="devasa")

        self.assertIn(f"et-{etiket_modulu.VARSAYILAN_OLCU}", govde)

    def test_varsayilan_dukkandaki_etiket_yazicisi(self):
        """Gunluk is Xprinter XP-470B'den cikiyor: 95 x 39 mm rulo, tek tek."""
        govde = self._govde(ids=str(self.urun.pk))

        self.assertIn("@page{size:95mm 39mm;margin:0}", govde)
        self.assertIn("et-termal", govde)
        self.assertIn("et-tek", govde)

    def test_varsayilan_isim_seridi_beyaz(self):
        """Termal kafa bos yere yanmasin: ad siyah zemin yerine altciizgili.
        Siyah serit isteyen kutuyu isaretler."""
        beyaz = self._govde(ids=str(self.urun.pk))
        siyah = self._govde(ids=str(self.urun.pk), serit="1")

        # Tirnak sart: CSS blogu her iki sinifin kurallarini da tasiyor,
        # aranan sey kagida basilan kapsayicinin class'i.
        self.assertIn('et-cizgili"', beyaz)
        self.assertNotIn('et-seritli"', beyaz)
        self.assertIn('et-seritli"', siyah)

    def test_tek_duzende_her_etiket_ayri_sayfaya_gider(self):
        govde = self._govde(ids=str(self.urun.pk), duzen="tek")

        self.assertIn("break-after:page", govde)

    def test_a4_duzeninde_kagit_a4_olur(self):
        govde = self._govde(ids=str(self.urun.pk), duzen="sayfa", boyut="orta")

        self.assertIn("@page{size:A4 portrait;margin:6mm}", govde)
        self.assertNotIn("break-after:page", govde)

    def test_tek_duzende_bastan_bos_birakilmaz(self):
        """Rulodaki etiketin "sayfa basi" diye bir yeri yok."""
        govde = self._govde(ids=str(self.urun.pk), duzen="tek", atla="5")

        self.assertNotIn('<div class="etiket-bos">', govde)

    def test_bilinmeyen_duzen_varsayilana_duser(self):
        govde = self._govde(ids=str(self.urun.pk), duzen="rulo-mu-ne")

        self.assertIn("et-tek", govde)

    def test_bastan_bos_birakma(self):
        """Yarim kalmis etiket sayfasi tekrar kullanilabilsin."""
        govde = self._govde(ids=str(self.urun.pk), duzen="sayfa", atla="5")

        self.assertEqual(govde.count('<div class="etiket-bos">'), 5)

    def test_arama_ile_urun_bulunur(self):
        govde = self._govde(q="Silgi")

        self.assertIn("<span>Silgi</span>", govde)
        self.assertNotIn("<span>Lets 6 Renk Guaj Boya 25ml</span>", govde)

    def test_secim_yoksa_yol_gosterilir(self):
        govde = self._govde()

        self.assertIn("Etiket basılacak ürün seçilmedi", govde)
        self.assertNotIn('<article class="etiket">', govde)

    def test_kontrol_hanesi_bozuk_barkod_sayfayi_dusurmez(self):
        bozuk = Stok.objects.create(Urun_Adi="Dahili Kod", Barkod=4071, Tutar=5)
        govde = self._govde(ids=str(bozuk.pk))

        self.assertIn("4071", govde)
        self.assertIn("<svg", govde)

    def test_tek_sorguyla_urunler_cekilir(self):
        """Etiket sayfasi yuzlerce urunle acilabiliyor; her urun icin ayri
        sorgu acilmamali."""
        idler = ",".join(str(u.pk) for u in Stok.objects.all())

        with self.assertNumQueries(3):   # oturum + kullanici + urunler
            self.client.get(reverse("etiket"), {"ids": idler})

    def test_barkod_termal_kafaya_gore_ciziliyor(self):
        """Kenar yumusatma 203 dpi tek bit kafada cubuk genisligini kaydiriyor;
        SVG crispEdges olmadan basilan barkod okunmuyor."""
        govde = self._govde(ids=str(self.urun.pk))

        self.assertIn('shape-rendering="crispEdges"', govde)
        # Barkodun genisligi modul sayisindan hesaplaniyor, sutuna esnetilmiyor.
        self.assertIn("--barkod-modul:113", govde)

    def test_barkod_turleri_ekranda_sayiliyor(self):
        """Hepsi Code 128 cikiyorsa barkod verisinde sorun var demektir;
        kullanici bunu ekranda gorsun."""
        govde = self._govde(ids=f"{self.urun.pk},{self.ikinci.pk}")

        self.assertIn("EAN-13: 1", govde)      # 8680679801027 gecerli
        self.assertIn("Code 128: 1", govde)    # 8690000000002 kontrol hanesi tutmuyor


class EtiketOlcuBaskisiTesti(TestCase):
    """Sinama etiketi ve baski kaydirma -- yazicinin kagidi kacirdigi durumlar."""

    def setUp(self):
        User.objects.create_user("kasa", password="kasa-sifresi-123")
        self.client.login(username="kasa", password="kasa-sifresi-123")
        self.urun = Stok.objects.create(
            Urun_Adi="Silgi", Barkod=8680679801027, Tutar=Decimal("12.50"))

    def _govde(self, **parametreler):
        cevap = self.client.get(reverse("etiket"), parametreler)
        self.assertEqual(cevap.status_code, 200)
        return cevap.content.decode()

    def test_sinama_cetvelli_tek_etiket_basar(self):
        govde = self._govde(sinama="1", ids=str(self.urun.pk))

        self.assertIn("et-sinama", govde)
        self.assertIn("SOL ÜST", govde)
        self.assertIn("SAĞ ALT", govde)
        self.assertIn("82 × 39 mm", govde)             # kagit degil, basilan alan
        self.assertIn('style="left:80mm"', govde)      # yatay cetvel kenara kadar
        self.assertIn('style="top:35mm"', govde)       # dikey cetvel kenara kadar
        # Uc numarali etiket: aralarinda bos etiket kalip kalmadigi goruluyor.
        self.assertEqual(govde.count('class="et-sinama"'), 3)
        for sira in (1, 2, 3):
            self.assertIn(f"{sira}. etiket ·", govde)
        # Urun etiketi basilmaz: 600 urun secili olsa da barkod cizilmesin.
        self.assertNotIn("KDV Dahildir.", govde)

    def test_sinama_kapaliyken_urun_etiketi_cikar(self):
        govde = self._govde(ids=str(self.urun.pk))

        self.assertIn("KDV Dahildir.", govde)
        self.assertNotIn('class="et-sinama"', govde)

    def test_kaydirma_css_e_noktali_yaziliyor(self):
        """Turkce yerellestirmede {{ 1.5 }} "1,5" basar, o da gecersiz CSS."""
        govde = self._govde(ids=str(self.urun.pk), kx="2.5", ky="-3")

        self.assertIn("--et-kx:2.5mm;--et-ky:-3mm", govde)

    def test_kaydirma_virgullu_de_kabul_edilir(self):
        self.assertIn("--et-kx:1.5mm", self._govde(ids=str(self.urun.pk), kx="1,5"))

    def test_kaydirma_sinirlari_ve_copu_olcunun_varsayilanina_duser(self):
        """Cop deger CSS'e sizmasin; sinirlar disi deger sinira otursun."""
        varsayilan = "%g" % etiket_modulu.OLCULER["termal"]["kaydirma_x"]

        for deger, beklenen in (("500", "20"), ("-500", "-20"),
                                ("abc", varsayilan), ("NaN", varsayilan),
                                ("inf", varsayilan)):
            with self.subTest(deger=deger):
                govde = self._govde(ids=str(self.urun.pk), kx=deger)

                self.assertIn(f"--et-kx:{beklenen}mm", govde)

    def test_kaydirma_baskida_uygulaniyor(self):
        govde = self._govde(ids=str(self.urun.pk), kx="2", ky="2")

        self.assertIn("left:var(--et-kx,0);top:var(--et-ky,0)", govde)

    def test_dukkandaki_etiketin_boyu_varsayilan_geliyor(self):
        """Baska sehirdeki kullanici hicbir kutu doldurmadan dogru etiket
        bassin: kullanilabilir boy olcuye gomulu, kaydirma sifir."""
        govde = self._govde(ids=str(self.urun.pk))

        self.assertIn("--et-g:82mm", govde)
        self.assertIn("--et-kx:0mm", govde)

    def test_tasarim_boyu_kagittan_uzun_olamaz(self):
        """Kagidi asan tasarimin fazlasi zaten basilmaz; sinira otursun."""
        govde = self._govde(ids=str(self.urun.pk), boy="300")

        self.assertIn("--et-g:95mm", govde)

    def test_tasarim_boyu_degistirilebiliyor(self):
        govde = self._govde(ids=str(self.urun.pk), boy="88,5")

        self.assertIn("--et-g:88.5mm", govde)

    def test_a4_dizilisinde_tasarim_boyu_kagidin_kendisi(self):
        """A4'te etiketler kesilmis geliyor: boy kagida esit olmali."""
        govde = self._govde(ids=str(self.urun.pk), boyut="orta", duzen="sayfa", boy="30")

        self.assertIn("--et-g:66mm", govde)

    def test_a4_olculerinde_kaydirma_yok(self):
        govde = self._govde(ids=str(self.urun.pk), boyut="orta", duzen="sayfa")

        self.assertIn("--et-kx:0mm", govde)

    def test_ayarlar_oturumda_hatirlaniyor(self):
        """Admin eylemi /etiket/'e parametresiz yonlendiriyor; bir kere kurulan
        ayar her baskida gecerli olmali."""
        self._govde(ids=str(self.urun.pk), kx="-6.5", boy="60", boyut="orta", serit="1")

        govde = self._govde(ids=str(self.urun.pk))

        self.assertIn("--et-kx:-6.5mm", govde)
        self.assertIn("--et-g:60mm", govde)
        self.assertIn('et-orta', govde)
        self.assertIn('et-seritli"', govde)

    def test_kopya_sayisi_hatirlanmaz(self):
        """Bir kere 5 kopya basan, sonraki her uruni 5 kopya basmasin."""
        self._govde(ids=str(self.urun.pk), kopya="5")

        self.assertEqual(self._govde(ids=str(self.urun.pk)).count("KDV Dahildir."), 1)

    def test_bas_parametresi_kendiliginden_yazdirir(self):
        self.assertIn("window.print()", self._govde(ids=str(self.urun.pk), bas="1"))

    def test_bas_verilmezse_kendiliginden_yazdirmaz(self):
        govde = self._govde(ids=str(self.urun.pk))

        self.assertNotIn("requestAnimationFrame", govde)


class EtiketAdminEylemiTesti(TestCase):
    """Admin'deki 'raf etiketi yazdir' eylemi."""

    def setUp(self):
        User.objects.create_superuser("yonetici", "y@o.com", "gizli-sifre-123")
        self.client.login(username="yonetici", password="gizli-sifre-123")
        self.urun = Stok.objects.create(Urun_Adi="Defter", Barkod=8690000000010, Tutar=45)

    def test_eylem_etiket_sayfasina_gonderir(self):
        cevap = self.client.post("/admin/stok/stok/", {
            "action": "etiket_yazdir",
            "_selected_action": [str(self.urun.pk)],
        })

        self.assertRedirects(cevap, reverse("etiket"))
        self.assertEqual(
            self.client.session[etiket_modulu.OTURUM_ANAHTARI], [self.urun.pk])

    def test_secim_url_yerine_oturumda_tasinir(self):
        """'Tumunu sec' ile yuzlerce urun secilince adres satiri tasmasin."""
        cevap = self.client.post("/admin/stok/stok/", {
            "action": "etiket_yazdir",
            "_selected_action": [str(self.urun.pk)],
        })

        self.assertNotIn("ids=", cevap["Location"])

    def test_listedeki_baglanti_dogrudan_yazdiriyor(self):
        """Kasadaki kisi sayfayla ugrasmasin: tik -> yazdirma penceresi."""
        cevap = self.client.get(reverse("admin:stok_stok_changelist"))

        self.assertIn(f"{reverse('etiket')}?ids={self.urun.pk}&amp;bas=1",
                      cevap.content.decode())

    def test_listede_tek_urunluk_etiket_baglantisi_var(self):
        govde = self.client.get("/admin/stok/stok/").content.decode()

        self.assertIn(f"{reverse('etiket')}?ids={self.urun.pk}", govde)
