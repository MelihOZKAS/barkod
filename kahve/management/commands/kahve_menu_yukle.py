"""Menuyu tek seferde kurar.

    python manage.py kahve_menu_yukle            # ne olacagini gosterir
    python manage.py kahve_menu_yukle --uygula   # gercekten ekler

Tekrar calistirilabilir: var olan urunlerin SADECE fiyati, sirasi ve kategorisi
guncellenir.
Isaretledigin "Hediye sayacina +1" kutusu, yukledigin gorsel, yazdigin aciklama
ve icindekiler korunur — ustune yazilmaz.

Damga bayragi bilerek ayarlanmiyor; hangi icecek hediye kazandiracak, admin'den
sen seciyorsun. Kahvelerin hepsini birden acmak istersen: --kahvelere-damga
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from kahve.models import Kahve, KahveKategori

# (ad, fiyat, damga_onerisi)  — damga_onerisi sadece --kahvelere-damga ile kullanilir
SICAK = [
    ("Espresso", 70, True),
    ("Americano", 70, True),
    ("Cappuccino", 80, True),
    ("Flat White", 80, True),
    ("Latte", 80, True),
    ("Karamel Macchiato", 100, True),
    ("Fındıklı Latte", 90, True),
    ("Salt Karamel Latte", 90, True),
    ("Lotuslu Latte", 90, True),
    ("Mocha", 100, True),
    ("White Chocolate Mocha", 100, True),
    ("Türk Kahvesi", 40, True),
    ("3'ü 1 Arada", 25, False),
    ("Çay", 20, False),
]

SOGUK = [
    ("Iced Espresso", 70, True),
    ("Iced Americano", 70, True),
    ("Iced Flat White", 70, True),
    ("Iced Latte", 80, True),
    ("Iced Latte Vanilya", 90, True),
    ("Iced Latte Karamel", 90, True),
    ("Iced Latte Fındıklı", 90, True),
    ("Iced Latte Salt Karamel", 90, True),
    ("Iced Latte Lotuslu", 90, True),
    ("Iced Mocha", 100, True),
    ("Iced White Chocolate Mocha", 100, True),
    ("Iced Karamel Macchiato", 100, True),
]

EKSTRA = [
    ("Ekstra Shot", 20, False),
    ("Şurup", 10, False),
    ("Sos", 10, False),
]

BOLUMLER = [("Sıcak içecekler", SICAK), ("Soğuk içecekler", SOGUK), ("Ekstralar", EKSTRA)]


class Command(BaseCommand):
    help = "Kahve menusunu tek seferde kurar. Varsayilan kuru calisma."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument(
            "--uygula", action="store_true",
            help="Degisiklikleri gercekten kaydet. Verilmezse sadece listelenir.",
        )
        ayristirici.add_argument(
            "--kahvelere-damga", action="store_true",
            help="Yeni eklenen kahvelerde 'Hediye sayacina +1' acik gelsin "
                 "(cay, 3'u 1 arada ve ekstralar haric).",
        )

    def handle(self, *args, **secenekler):
        uygula = secenekler["uygula"]
        damga_ver = secenekler["kahvelere_damga"]
        sessiz = secenekler.get("verbosity", 1) == 0

        mevcut = {ad: k for ad, k in Kahve.objects.values_list("ad", "id")}
        kategoriler = {}
        yeni, guncel = [], []
        sira = 0

        with transaction.atomic():
            for bolum_sira, (bolum_adi, urunler) in enumerate(BOLUMLER):
                kategori, _ = KahveKategori.objects.get_or_create(
                    ad=bolum_adi, defaults={"sira": bolum_sira}
                )
                kategoriler[bolum_adi] = kategori
                if not sessiz:
                    self.stdout.write(self.style.MIGRATE_HEADING(f"\n  {bolum_adi}"))
                for ad, fiyat, damga_onerisi in urunler:
                    sira += 1
                    var_mi = ad in mevcut
                    if var_mi:
                        guncel.append(ad)
                        durum = "fiyat guncellendi"
                    else:
                        yeni.append(ad)
                        durum = "YENI"
                        if damga_ver and damga_onerisi:
                            durum += " (+1 acik)"

                    if not sessiz:
                        self.stdout.write(f"    {ad:<30}{fiyat:>4} TL   {durum}")

                    if not uygula:
                        continue

                    if var_mi:
                        # Sadece fiyat, sira ve kategori: bayraklari, gorseli,
                        # aciklamayi bozma.
                        Kahve.objects.filter(ad=ad).update(
                            fiyat=Decimal(fiyat), sira=sira, kategori=kategori
                        )
                    else:
                        Kahve.objects.create(
                            ad=ad,
                            fiyat=Decimal(fiyat),
                            sira=sira,
                            aktif=True,
                            kategori=kategori,
                            damga_veriyor=bool(damga_ver and damga_onerisi),
                        )

            if not uygula:
                transaction.set_rollback(True)

        if sessiz:
            return

        if uygula:
            self.stdout.write(self.style.SUCCESS(
                f"\n  {len(yeni)} ürün eklendi, {len(guncel)} ürünün fiyatı güncellendi."
            ))
            self.stdout.write(
                "\n  Sırada sende:\n"
                "    1. Admin > Kahveler > her ürüne fotoğraf yükle\n"
                "    2. Listeden 'Hediye sayacına +1' kutularını işaretle"
                + (" (kahvelerde zaten açık)" if damga_ver else "")
                + "\n    3. İstersen açıklama ve içindekileri yaz"
            )
        else:
            self.stdout.write(self.style.WARNING(
                f"\n  Kuru çalışma: {len(yeni)} yeni, {len(guncel)} güncelleme. "
                "Hiçbir şey kaydedilmedi.\n"
                "  Uygulamak için: --uygula   (kahvelerde +1 açık gelsin: --kahvelere-damga)"
            ))
