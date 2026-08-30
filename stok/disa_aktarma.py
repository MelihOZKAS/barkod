"""Stok urunlerinin CSV bicimi.

Hem yonetim komutu (stok_disa_aktar) hem de admin'deki "CSV olarak indir"
eylemi buradan okur. Boylece admin'den indirilen dosya stok_ice_aktar ile
geri yuklenebilir.
"""

import csv

BASLIKLAR = [
    "barkod", "urun_adi", "tutar", "liste_grup", "gruplar",
    "favori", "stok_durumu", "oto_sil",
]


def urun_satiri(urun):
    return {
        "barkod": urun.Barkod,
        "urun_adi": urun.Urun_Adi,
        "tutar": urun.Tutar if urun.Tutar is not None else "",
        "liste_grup": urun.Liste_grup.Grup_Adi if urun.Liste_grup_id else "",
        "gruplar": " | ".join(g.Grup_Adi for g in urun.Grup.all()),
        "favori": "evet" if urun.Favori else "hayir",
        "stok_durumu": "evet" if urun.Stok_Durumu else "hayir",
        "oto_sil": "evet" if urun.Oto_Sil else "hayir",
    }


def urunleri_yaz(dosya, urunler):
    """Urunleri acik bir dosyaya CSV olarak yazar, kac satir yazdigini doner."""
    yazici = csv.DictWriter(dosya, fieldnames=BASLIKLAR)
    yazici.writeheader()
    sayi = 0
    for urun in urunler:
        yazici.writerow(urun_satiri(urun))
        sayi += 1
    return sayi


def hazir_sorgu(sorgu):
    """N+1 olmasin diye grup iliskilerini onceden ceker."""
    return sorgu.select_related("Liste_grup").prefetch_related("Grup")
