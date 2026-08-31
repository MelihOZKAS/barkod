"""Yuklenmis urun fotograflarini yeniden sikistirir.

Menu fotograflari PNG olarak ~1,7 MB duruyordu; 30 urunluk menu mobil
uygulamada 50 MB indiriyordu. Bu komut var olan dosyalari kare kirpip
JPEG'e ceviriyor - yeni yuklemeler zaten oyle kaydediliyor.

    python manage.py kahve_gorsel_sikistir            # ne olacagini gosterir
    python manage.py kahve_gorsel_sikistir --uygula   # gercekten uygular

Varsayilan kuru calisma: --uygula vermeden hicbir dosyaya dokunulmaz.
"""

import os

from django.core.management.base import BaseCommand

from kahve.models import Kahve


def _boyut(yol):
    try:
        return os.path.getsize(yol)
    except OSError:
        return 0


class Command(BaseCommand):
    help = "Urun fotograflarini kare kirpip JPEG'e cevirir. Varsayilan kuru calisma."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument(
            "--uygula", action="store_true",
            help="Degisiklikleri gercekten kaydet. Verilmezse sadece listelenir.",
        )

    def handle(self, *args, **secenekler):
        uygula = secenekler["uygula"]
        onceki_toplam = sonraki_toplam = 0
        islenen = 0

        for kahve in Kahve.objects.exclude(gorsel="").exclude(gorsel__isnull=True):
            try:
                yol = kahve.gorsel.path
            except (NotImplementedError, ValueError):
                continue
            onceki = _boyut(yol)
            if not onceki:
                continue

            if not uygula:
                onceki_toplam += onceki
                islenen += 1
                self.stdout.write(f"  {onceki / 1024:8.0f} KB  {kahve.ad}")
                continue

            kahve._gorseli_kucult()
            try:
                sonraki = _boyut(kahve.gorsel.path)
            except (NotImplementedError, ValueError):
                sonraki = onceki

            onceki_toplam += onceki
            sonraki_toplam += sonraki
            islenen += 1
            self.stdout.write(
                f"  {onceki / 1024:8.0f} KB → {sonraki / 1024:6.0f} KB  {kahve.ad}"
            )

        if not islenen:
            self.stdout.write("Fotografi olan ürün yok.")
            return

        if not uygula:
            self.stdout.write("")
            self.stdout.write(
                f"{islenen} fotoğraf, toplam {onceki_toplam / 1024 / 1024:.1f} MB. "
                "Uygulamak için --uygula ekleyin."
            )
            return

        kazanc = onceki_toplam - sonraki_toplam
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"{islenen} fotoğraf: {onceki_toplam / 1024 / 1024:.1f} MB → "
            f"{sonraki_toplam / 1024 / 1024:.1f} MB "
            f"({kazanc / 1024 / 1024:.1f} MB kazanç)"
        ))
