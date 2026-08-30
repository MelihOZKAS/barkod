"""Hicbir urune bagli olmayan oksuz gorselleri bulur ve silebilir.

Varsayilan olarak sadece listeler, silmez:
    python manage.py gorsel_temizle
Gercekten silmek icin:
    python manage.py gorsel_temizle --sil
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from kahve.models import Kahve


class Command(BaseCommand):
    help = "Kahve gorselleri klasorundeki oksuz dosyalari listeler veya siler."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument(
            "--sil",
            action="store_true",
            help="Dosyalari gercekten sil. Verilmezse sadece listelenir.",
        )

    def handle(self, *args, **secenekler):
        sessiz = secenekler.get("verbosity", 1) == 0
        klasor = Path(settings.MEDIA_ROOT) / "kahve"
        if not klasor.is_dir():
            if not sessiz:
                self.stdout.write("Gorsel klasoru henuz olusmamis, temizlenecek bir sey yok.")
            return

        kullanilan = {
            Path(ad).name
            for ad in Kahve.objects.exclude(gorsel="").values_list("gorsel", flat=True)
            if ad
        }
        diskteki = {yol for yol in klasor.iterdir() if yol.is_file() and not yol.name.startswith(".")}
        oksuzler = sorted(yol for yol in diskteki if yol.name not in kullanilan)

        if not oksuzler:
            if not sessiz:
                self.stdout.write(
                    self.style.SUCCESS(f"Temiz: {len(diskteki)} dosyanin hepsi bir urune bagli.")
                )
            return

        toplam = sum(yol.stat().st_size for yol in oksuzler)
        if not sessiz:
            for yol in oksuzler:
                self.stdout.write(f"  {yol.name}  ({yol.stat().st_size // 1024} KB)")

        if secenekler["sil"]:
            for yol in oksuzler:
                yol.unlink()
            if not sessiz:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n{len(oksuzler)} oksuz dosya silindi, {toplam // 1024} KB yer acildi."
                    )
                )
        elif not sessiz:
            self.stdout.write(
                self.style.WARNING(
                    f"\n{len(oksuzler)} oksuz dosya bulundu ({toplam // 1024} KB). "
                    "Silmek icin: python manage.py gorsel_temizle --sil"
                )
            )
