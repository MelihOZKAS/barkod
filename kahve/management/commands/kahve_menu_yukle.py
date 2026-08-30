"""Menuyu tek seferde kurar (komut satirindan).

    python manage.py kahve_menu_yukle            # ne olacagini gosterir
    python manage.py kahve_menu_yukle --uygula   # gercekten ekler

Ayni isi personel ekranindan da yapabilirsin: /kahve/kasa/menu-yukle/

Tekrar calistirilabilir: var olan urunlerin SADECE fiyati, sirasi ve kategorisi
guncellenir. Isaretledigin "Hediye sayacina +1" kutusu, yukledigin gorsel,
yazdigin aciklama ve icindekiler korunur — ustune yazilmaz.
"""

from django.core.management.base import BaseCommand

from kahve.menu_verisi import yukle


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
        sessiz = secenekler.get("verbosity", 1) == 0
        sonuc = yukle(uygula=uygula, kahvelere_damga=secenekler["kahvelere_damga"])

        if not sessiz:
            for bolum in sonuc["bolumler"]:
                self.stdout.write(self.style.MIGRATE_HEADING(f"\n  {bolum['ad']}"))
                for u in bolum["urunler"]:
                    durum = "YENI" if u["yeni"] else "fiyat guncellendi"
                    self.stdout.write(f"    {u['ad']:<30}{u['fiyat']:>4} TL   {durum}")

        if sessiz:
            return

        yeni, guncel = len(sonuc["yeni"]), len(sonuc["guncel"])
        if uygula:
            self.stdout.write(self.style.SUCCESS(
                f"\n  {yeni} ürün eklendi, {guncel} ürünün fiyatı güncellendi."
            ))
            self.stdout.write(
                "\n  Sırada sende:\n"
                "    1. Admin > Kahveler > her ürüne fotoğraf yükle\n"
                "    2. Listeden 'Hediye sayacına +1' kutularını işaretle"
            )
        else:
            self.stdout.write(self.style.WARNING(
                f"\n  Kuru çalışma: {yeni} yeni, {guncel} güncelleme. Hiçbir şey kaydedilmedi.\n"
                "  Uygulamak için: --uygula   (kahvelerde +1 açık gelsin: --kahvelere-damga)"
            ))
