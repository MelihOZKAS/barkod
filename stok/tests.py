"""Sepet miktar guncelleme testleri.

Bu uc nokta canli kasada kullaniliyor: miktar alani <select> iken gecersiz
deger gelmesi imkansizdi, <input type=number> olunca mumkun hale geldi.
Testler o sinirlari koruyor.

Calistirmak icin:
    python manage.py test stok
"""

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
