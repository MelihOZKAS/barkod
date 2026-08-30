"""Stok urunlerini ve gruplarini disa aktarir.

    python manage.py stok_disa_aktar
    python manage.py stok_disa_aktar --klasor /yol/yedek

Uretilen klasor:
    urunler.csv         Barkod, ad, fiyat, gruplar (Excel'de acilir)
    liste-gruplari.csv  Liste Favori Gruplari
    urun-gruplari.csv   Urun Gruplari
    tum-veri.json       Uc tablonun tamami (loaddata uyumlu, birebir geri yukleme)
"""

import csv
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand

from stok.disa_aktarma import hazir_sorgu, urunleri_yaz
from stok.models import Liste_Grup, Stok, UrunGruplari


class Command(BaseCommand):
    help = "Stok urunlerini ve gruplarini bir klasore aktarir."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument(
            "--klasor",
            default=None,
            help="Yedegin yazilacagi klasor. Verilmezse yedek/stok-<tarih>/ kullanilir.",
        )

    def handle(self, *args, **secenekler):
        sessiz = secenekler.get("verbosity", 1) == 0
        damga = datetime.now().strftime("%Y%m%d-%H%M")
        klasor = Path(secenekler["klasor"] or Path(settings.BASE_DIR) / "yedek" / f"stok-{damga}")
        klasor.mkdir(parents=True, exist_ok=True)

        urun_sayisi = self._urunleri_yaz(klasor / "urunler.csv")
        liste_sayisi = self._gruplari_yaz(klasor / "liste-gruplari.csv", Liste_Grup)
        grup_sayisi = self._gruplari_yaz(klasor / "urun-gruplari.csv", UrunGruplari)
        kayit_sayisi = self._tum_veriyi_yaz(klasor / "tum-veri.json")

        if sessiz:
            return
        self.stdout.write(self.style.SUCCESS(f"\nYedek hazir: {klasor}"))
        self.stdout.write(f"  urunler.csv         {urun_sayisi} urun")
        self.stdout.write(f"  liste-gruplari.csv  {liste_sayisi} grup")
        self.stdout.write(f"  urun-gruplari.csv   {grup_sayisi} grup")
        self.stdout.write(f"  tum-veri.json       {kayit_sayisi} kayit")
        self.stdout.write(
            "\nGeri yuklemek icin:\n"
            f"  python manage.py stok_ice_aktar {klasor / 'urunler.csv'}\n"
            f"  python manage.py stok_ice_aktar {klasor / 'urunler.csv'} --uygula"
        )

    def _urunleri_yaz(self, yol):
        urunler = hazir_sorgu(Stok.objects.order_by("Urun_Adi"))
        with yol.open("w", newline="", encoding="utf-8-sig") as dosya:
            return urunleri_yaz(dosya, urunler.iterator(chunk_size=500))

    def _gruplari_yaz(self, yol, model):
        adlar = list(model.objects.order_by("Grup_Adi").values_list("Grup_Adi", flat=True))
        with yol.open("w", newline="", encoding="utf-8-sig") as dosya:
            yazici = csv.writer(dosya)
            yazici.writerow(["grup_adi"])
            for ad in adlar:
                yazici.writerow([ad])
        return len(adlar)

    def _tum_veriyi_yaz(self, yol):
        nesneler = []
        for model in (UrunGruplari, Liste_Grup, Stok):
            nesneler.extend(model.objects.all())
        with yol.open("w", encoding="utf-8") as dosya:
            serializers.serialize("json", nesneler, stream=dosya, indent=2)
        return len(nesneler)
