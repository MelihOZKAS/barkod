"""Stok urunlerini CSV'den geri yukler.

Varsayilan olarak SADECE ne olacagini gosterir:
    python manage.py stok_ice_aktar yedek/urunler.csv
Gercekten uygulamak icin:
    python manage.py stok_ice_aktar yedek/urunler.csv --uygula

Urunler BARKODA gore eslesir: ayni barkod varsa guncellenir, yoksa olusturulur.
Eksik gruplar otomatik acilir. Ayni klasorde liste-gruplari.csv / urun-gruplari.csv
varsa onlar da okunur; boylece hic urunu olmayan gruplar da geri gelir.

NOT: Kayitlar tek tek save() ile yazilir; Stok.save() arama alani Urun_Genel'i
hesapladigi icin toplu ekleme (bulk_create) kullanilamaz, yoksa arama bozulur.
"""

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from stok.models import Liste_Grup, Stok, UrunGruplari

EVET = {"evet", "true", "1", "acik", "yes", "var"}


def _bool(deger, varsayilan=False):
    metin = (deger or "").strip().lower()
    return varsayilan if not metin else metin in EVET


class Command(BaseCommand):
    help = "Stok urunlerini CSV'den ice aktarir. Varsayilan kuru calisma."

    def add_arguments(self, ayristirici):
        ayristirici.add_argument("dosya", help="urunler.csv yolu")
        ayristirici.add_argument(
            "--uygula",
            action="store_true",
            help="Degisiklikleri gercekten kaydet. Verilmezse sadece ozet gosterilir.",
        )

    def handle(self, *args, **secenekler):
        yol = Path(secenekler["dosya"])
        if not yol.is_file():
            raise CommandError(f"Dosya bulunamadi: {yol}")

        uygula = secenekler["uygula"]
        sessiz = secenekler.get("verbosity", 1) == 0

        satirlar, hatali = self._oku(yol)
        mevcut_barkodlar = set(
            Stok.objects.filter(Barkod__in=[s["barkod"] for s in satirlar])
            .values_list("Barkod", flat=True)
        )
        yeni = [s for s in satirlar if s["barkod"] not in mevcut_barkodlar]
        guncel = [s for s in satirlar if s["barkod"] in mevcut_barkodlar]

        # Urunlerde gecen gruplar + yanindaki grup dosyalarindakiler.
        # Ikincisi olmasa hic urunu olmayan gruplar geri gelmezdi.
        gerekli_liste = {s["liste_grup"] for s in satirlar if s["liste_grup"]}
        gerekli_liste |= self._grup_dosyasi(yol.parent / "liste-gruplari.csv")
        gerekli_grup = {g for s in satirlar for g in s["gruplar"]}
        gerekli_grup |= self._grup_dosyasi(yol.parent / "urun-gruplari.csv")
        eksik_liste = gerekli_liste - set(Liste_Grup.objects.values_list("Grup_Adi", flat=True))
        eksik_grup = gerekli_grup - set(UrunGruplari.objects.values_list("Grup_Adi", flat=True))

        if not sessiz:
            for hata in hatali[:20]:
                self.stdout.write(self.style.ERROR(f"  ATLANDI  {hata}"))
            if len(hatali) > 20:
                self.stdout.write(self.style.ERROR(f"  ... {len(hatali) - 20} hatali satir daha"))
            self.stdout.write(
                f"\n  {len(yeni)} yeni ürün, {len(guncel)} güncelleme, {len(hatali)} hatalı satır\n"
                f"  {len(eksik_liste)} yeni liste grubu, {len(eksik_grup)} yeni ürün grubu açılacak"
            )

        if not uygula:
            if not sessiz:
                self.stdout.write(
                    self.style.WARNING(
                        "\nKuru çalışma — hiçbir şey kaydedilmedi.\n"
                        "Uygulamak için sonuna --uygula ekleyin."
                    )
                )
            return

        with transaction.atomic():
            for ad in eksik_liste:
                Liste_Grup.objects.get_or_create(Grup_Adi=ad)
            for ad in eksik_grup:
                UrunGruplari.objects.get_or_create(Grup_Adi=ad)

            listeler = {g.Grup_Adi: g for g in Liste_Grup.objects.all()}
            gruplar = {g.Grup_Adi: g for g in UrunGruplari.objects.all()}

            for satir in satirlar:
                urun, _ = Stok.objects.update_or_create(
                    Barkod=satir["barkod"],
                    defaults={
                        "Urun_Adi": satir["urun_adi"],
                        "Tutar": satir["tutar"],
                        "Liste_grup": listeler.get(satir["liste_grup"]),
                        "Favori": satir["favori"],
                        "Stok_Durumu": satir["stok_durumu"],
                        "Oto_Sil": satir["oto_sil"],
                    },
                )
                urun.Grup.set([gruplar[a] for a in satir["gruplar"] if a in gruplar])

        if sessiz:
            return
        self.stdout.write(
            self.style.SUCCESS(f"\n{len(yeni)} ürün eklendi, {len(guncel)} ürün güncellendi.")
        )
        if hatali:
            self.stdout.write(self.style.WARNING(f"{len(hatali)} satır atlandı."))

    def _grup_dosyasi(self, yol):
        """Yanindaki grup CSV'sini okur. Yoksa bos kume doner."""
        if not yol.is_file():
            return set()
        with yol.open(encoding="utf-8-sig", newline="") as dosya:
            return {
                (satir.get("grup_adi") or "").strip()
                for satir in csv.DictReader(dosya)
                if (satir.get("grup_adi") or "").strip()
            }

    def _oku(self, yol):
        satirlar, hatali = [], []
        with yol.open(encoding="utf-8-sig", newline="") as dosya:
            for satir_no, satir in enumerate(csv.DictReader(dosya), start=2):
                ham_barkod = (satir.get("barkod") or "").strip()
                ad = (satir.get("urun_adi") or "").strip()
                if not ham_barkod or not ad:
                    hatali.append(f"satır {satir_no}: barkod veya ürün adı boş")
                    continue
                if not ham_barkod.isdigit():
                    hatali.append(f"satır {satir_no}: barkod sayı değil ({ham_barkod!r})")
                    continue
                try:
                    ham_tutar = (satir.get("tutar") or "").replace(",", ".").strip()
                    tutar = Decimal(ham_tutar) if ham_tutar else Decimal("0.00")
                except InvalidOperation:
                    hatali.append(f"satır {satir_no}: '{ad}' fiyatı sayı değil ({satir.get('tutar')!r})")
                    continue

                satirlar.append({
                    "barkod": int(ham_barkod),
                    "urun_adi": ad,
                    "tutar": tutar,
                    "liste_grup": (satir.get("liste_grup") or "").strip(),
                    "gruplar": [g.strip() for g in (satir.get("gruplar") or "").split("|") if g.strip()],
                    "favori": _bool(satir.get("favori")),
                    "stok_durumu": _bool(satir.get("stok_durumu"), True),
                    "oto_sil": _bool(satir.get("oto_sil")),
                })
        return satirlar, hatali
