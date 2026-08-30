"""Kahve verisini disa aktarir: Excel'de duzenlenebilir CSV + tam yedek.

    python manage.py kahve_disa_aktar
    python manage.py kahve_disa_aktar --klasor /yol/yedek

Uretilen klasor:
    urunler.csv    Excel'de acilir, fiyat/aciklama toplu duzenlenebilir
    tum-veri.json  Musteriler, damgalar, satislar dahil her sey (loaddata uyumlu)
    gorseller/     Urun fotograflari
"""

import csv
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand

from kahve.models import HediyeKahve, Kahve, KahveAyar, KahveIcim, KahveMusteri, KahveSatis

BASLIKLAR = [
    "ad", "fiyat", "aciklama", "icindekiler", "sira",
    "aktif", "damga_veriyor", "hediye_gecerli", "gorsel",
]


class Command(BaseCommand):
    help = "Kahve urunlerini ve tum kahve verisini bir klasore aktarir."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument(
            "--klasor",
            default=None,
            help="Yedegin yazilacagi klasor. Verilmezse yedek/kahve-<tarih>/ kullanilir.",
        )

    def handle(self, *args, **secenekler):
        sessiz = secenekler.get("verbosity", 1) == 0
        damga = datetime.now().strftime("%Y%m%d-%H%M")
        klasor = Path(secenekler["klasor"] or Path(settings.BASE_DIR) / "yedek" / f"kahve-{damga}")
        klasor.mkdir(parents=True, exist_ok=True)

        urun_sayisi = self._urunleri_yaz(klasor / "urunler.csv")
        kayit_sayisi = self._tum_veriyi_yaz(klasor / "tum-veri.json")
        gorsel_sayisi = self._gorselleri_kopyala(klasor / "gorseller")

        if sessiz:
            return
        self.stdout.write(self.style.SUCCESS(f"\nYedek hazir: {klasor}"))
        self.stdout.write(f"  urunler.csv    {urun_sayisi} urun (Excel'de acilabilir)")
        self.stdout.write(f"  tum-veri.json  {kayit_sayisi} kayit")
        self.stdout.write(f"  gorseller/     {gorsel_sayisi} dosya")
        self.stdout.write(
            "\nGeri yuklemek icin:\n"
            f"  python manage.py kahve_ice_aktar {klasor / 'urunler.csv'}        (sadece urunler)\n"
            f"  python manage.py loaddata {klasor / 'tum-veri.json'}   (her sey)"
        )

    def _urunleri_yaz(self, yol):
        urunler = Kahve.objects.all().order_by("sira", "ad")
        with yol.open("w", newline="", encoding="utf-8-sig") as dosya:
            yazici = csv.DictWriter(dosya, fieldnames=BASLIKLAR)
            yazici.writeheader()
            for k in urunler:
                yazici.writerow({
                    "ad": k.ad,
                    "fiyat": k.fiyat,
                    "aciklama": k.aciklama,
                    # Excel'de tek hucrede dursun diye satirlari | ile birlestiriyoruz
                    "icindekiler": " | ".join(k.icindekiler_listesi),
                    "sira": k.sira,
                    "aktif": "evet" if k.aktif else "hayir",
                    "damga_veriyor": "evet" if k.damga_veriyor else "hayir",
                    "hediye_gecerli": "evet" if k.hediye_gecerli else "hayir",
                    "gorsel": Path(k.gorsel.name).name if k.gorsel else "",
                })
        return urunler.count()

    def _tum_veriyi_yaz(self, yol):
        nesneler = []
        for model in (KahveAyar, Kahve, KahveMusteri, KahveSatis, KahveIcim, HediyeKahve):
            nesneler.extend(model.objects.all())
        with yol.open("w", encoding="utf-8") as dosya:
            serializers.serialize("json", nesneler, stream=dosya, indent=2)
        return len(nesneler)

    def _gorselleri_kopyala(self, klasor):
        kaynak = Path(settings.MEDIA_ROOT) / "kahve"
        if not kaynak.is_dir():
            return 0
        klasor.mkdir(exist_ok=True)
        sayi = 0
        for dosya in kaynak.iterdir():
            if dosya.is_file() and not dosya.name.startswith("."):
                shutil.copy2(dosya, klasor / dosya.name)
                sayi += 1
        return sayi
