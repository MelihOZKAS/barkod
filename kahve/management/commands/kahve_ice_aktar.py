"""Urunleri CSV'den geri yukler (kahve_disa_aktar ciktisi ya da elle hazirlanmis).

Varsayilan olarak SADECE ne olacagini gosterir, veriyi degistirmez:
    python manage.py kahve_ice_aktar yedek/urunler.csv
Gercekten uygulamak icin:
    python manage.py kahve_ice_aktar yedek/urunler.csv --uygula

Urunler ADA gore eslesir: ayni adli urun varsa guncellenir, yoksa olusturulur.
Gorseller CSV ile tasinmaz; ayni klasordeki gorseller/ varsa oradan yuklenir.
"""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from kahve.models import Kahve

EVET = {"evet", "true", "1", "acik", "yes"}


def _bool(deger, varsayilan=False):
    metin = (deger or "").strip().lower()
    if not metin:
        return varsayilan
    return metin in EVET


class Command(BaseCommand):
    help = "Kahve urunlerini CSV'den ice aktarir. Varsayilan kuru calisma."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument("dosya", help="urunler.csv yolu")
        ayristirici.add_argument(
            "--uygula",
            action="store_true",
            help="Degisiklikleri gercekten kaydet. Verilmezse sadece listelenir.",
        )

    def handle(self, *args, **secenekler):
        yol = Path(secenekler["dosya"])
        if not yol.is_file():
            raise CommandError(f"Dosya bulunamadi: {yol}")

        gorsel_klasoru = yol.parent / "gorseller"
        uygula = secenekler["uygula"]
        sessiz = secenekler.get("verbosity", 1) == 0

        yeni, guncel, hatali = [], [], []

        with yol.open(encoding="utf-8-sig", newline="") as dosya:
            for satir_no, satir in enumerate(csv.DictReader(dosya), start=2):
                ad = (satir.get("ad") or "").strip()
                if not ad:
                    hatali.append(f"satir {satir_no}: ad bos")
                    continue
                try:
                    fiyat = Decimal((satir.get("fiyat") or "0").replace(",", ".").strip())
                except (InvalidOperation, AttributeError):
                    hatali.append(f"satir {satir_no}: '{ad}' fiyati sayi degil ({satir.get('fiyat')!r})")
                    continue

                alanlar = {
                    "fiyat": fiyat,
                    "aciklama": (satir.get("aciklama") or "").strip(),
                    "icindekiler": "\n".join(
                        p.strip() for p in (satir.get("icindekiler") or "").split("|") if p.strip()
                    ),
                    "sira": int(satir.get("sira") or 0),
                    "aktif": _bool(satir.get("aktif"), True),
                    "damga_veriyor": _bool(satir.get("damga_veriyor")),
                    "hediye_gecerli": _bool(satir.get("hediye_gecerli"), True),
                }
                mevcut = Kahve.objects.filter(ad=ad).first()
                (guncel if mevcut else yeni).append((ad, alanlar, satir.get("gorsel", "").strip()))

        if not sessiz:
            for hata in hatali:
                self.stdout.write(self.style.ERROR(f"  ATLANDI  {hata}"))
            for ad, alanlar, _ in yeni:
                self.stdout.write(f"  YENI     {ad}  {alanlar['fiyat']} TL")
            for ad, alanlar, _ in guncel:
                self.stdout.write(f"  GUNCELLE {ad}  {alanlar['fiyat']} TL")

        if not uygula:
            if sessiz:
                return
            self.stdout.write(
                self.style.WARNING(
                    f"\nKuru calisma: {len(yeni)} yeni, {len(guncel)} guncelleme, "
                    f"{len(hatali)} hatali satir. Hicbir sey kaydedilmedi.\n"
                    "Uygulamak icin sonuna --uygula ekleyin."
                )
            )
            return

        with transaction.atomic():
            for ad, alanlar, gorsel_adi in yeni + guncel:
                urun, _ = Kahve.objects.update_or_create(ad=ad, defaults=alanlar)
                self._gorseli_bagla(urun, gorsel_adi, gorsel_klasoru)

        if sessiz:
            return
        self.stdout.write(
            self.style.SUCCESS(f"\n{len(yeni)} urun eklendi, {len(guncel)} urun guncellendi.")
        )
        if hatali:
            self.stdout.write(self.style.WARNING(f"{len(hatali)} satir atlandi."))

    def _gorseli_bagla(self, urun, gorsel_adi, klasor):
        if not gorsel_adi or urun.gorsel:
            return  # gorsel yoksa ya da zaten varsa dokunma
        kaynak = klasor / gorsel_adi
        if not kaynak.is_file():
            return
        with kaynak.open("rb") as dosya:
            urun.gorsel.save(gorsel_adi, File(dosya), save=True)
