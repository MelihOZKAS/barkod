"""Menu listesi ve yukleme mantigi.

Hem yonetim komutu (kahve_menu_yukle) hem de personel ekranindaki
"Menuyu yukle" sayfasi buradan calisir; ikisi ayni sonucu uretir.
"""

from decimal import Decimal

from django.db import transaction

from .models import Kahve, KahveKategori

# (ad, fiyat, damga_onerisi)
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

BOLUMLER = [
    ("Sıcak İçecekler", SICAK),
    ("Soğuk İçecekler", SOGUK),
    ("Ekstralar", EKSTRA),
]




@transaction.atomic
def yukle(uygula=False, kahvelere_damga=False):
    """Menuyu kurar. uygula=False ise sadece ne olacagini hesaplar.

    Var olan urunlerin SADECE fiyati, sirasi ve kategorisi guncellenir;
    isaretlenmis damga bayragi, yuklenen gorsel ve yazilan aciklama korunur.
    """
    mevcut = set(Kahve.objects.values_list("ad", flat=True))
    sonuc = {"yeni": [], "guncel": [], "bolumler": []}
    sira = 0

    for bolum_sira, (bolum_adi, urunler) in enumerate(BOLUMLER):
        kategori = None
        if uygula:
            kategori, _ = KahveKategori.objects.get_or_create(
                ad=bolum_adi, defaults={"sira": bolum_sira}
            )
        satirlar = []
        for ad, fiyat, damga_onerisi in urunler:
            sira += 1
            var_mi = ad in mevcut
            (sonuc["guncel"] if var_mi else sonuc["yeni"]).append(ad)
            satirlar.append({"ad": ad, "fiyat": fiyat, "yeni": not var_mi})

            if not uygula:
                continue

            if var_mi:
                Kahve.objects.filter(ad=ad).update(
                    fiyat=Decimal(fiyat), sira=sira, kategori=kategori
                )
            else:
                Kahve.objects.create(
                    ad=ad, fiyat=Decimal(fiyat), sira=sira, aktif=True,
                    kategori=kategori,
                    damga_veriyor=bool(kahvelere_damga and damga_onerisi),
                )
        sonuc["bolumler"].append({"ad": bolum_adi, "urunler": satirlar})

    if not uygula:
        transaction.set_rollback(True)
    return sonuc
