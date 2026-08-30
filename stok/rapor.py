"""Kasa raporu: iki tezgahin parasi tek yerde.

Kirtasiye satislari (stok.Satis) ve kahve satislari (kahve.KahveSatis) ayri
tablolarda duruyor; rapor ikisini ayni bicime cevirip topluyor.

Borca yazilan tutar ciroya girer ama kasaya para olarak girmez - o yuzden
"nakit + kart" ile "ciro" birbirini tutmaz, ikisi ayri gosterilir.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone


def _sifirdan(deger):
    return deger or Decimal("0.00")


def _bos_ozet():
    return {
        "ciro": Decimal("0.00"),
        "nakit": Decimal("0.00"),
        "kart": Decimal("0.00"),
        "borc": Decimal("0.00"),
        "satis": 0,
    }


def _topla(sorgu, borc_degeri, borc_alani=None):
    """borc_alani verilirse borc o kolondan toplanir (parcali borc icin)."""
    borc_toplami = (
        Sum(borc_alani) if borc_alani
        else Sum("toplam", filter=Q(odeme_turu=borc_degeri))
    )
    toplamlar = sorgu.aggregate(
        ciro=Sum("toplam"),
        nakit=Sum("nakit_tutar"),
        kart=Sum("kart_tutar"),
        borc=borc_toplami,
        satis=Count("id"),
    )
    return {
        "ciro": _sifirdan(toplamlar["ciro"]),
        "nakit": _sifirdan(toplamlar["nakit"]),
        "kart": _sifirdan(toplamlar["kart"]),
        "borc": _sifirdan(toplamlar["borc"]),
        "satis": toplamlar["satis"] or 0,
    }


def aralik(donem, bugun=None):
    """donem: 'gun' | 'ay' | 'yil' -> (baslangic, bitis) - ikisi de dahil."""
    bugun = bugun or timezone.localtime().date()
    if donem == "yil":
        return date(bugun.year, 1, 1), bugun
    if donem == "ay":
        return date(bugun.year, bugun.month, 1), bugun
    return bugun, bugun


def ozet(baslangic, bitis):
    """Iki tezgahin toplamlari + ayri ayri dokumu."""
    from kahve.models import KahveSatis

    from .models import Satis

    kirtasiye = _topla(
        Satis.objects.filter(tarih__date__gte=baslangic, tarih__date__lte=bitis),
        Satis.Odeme.BORC,
        borc_alani="borc_tutar",
    )
    kahve = _topla(
        KahveSatis.objects.filter(tarih__date__gte=baslangic, tarih__date__lte=bitis),
        KahveSatis.Odeme.BORC,
    )
    toplam = {
        anahtar: kirtasiye[anahtar] + kahve[anahtar]
        for anahtar in ("ciro", "nakit", "kart", "borc", "satis")
    }
    return {"toplam": toplam, "kirtasiye": kirtasiye, "kahve": kahve}


def gunluk_seri(baslangic, bitis, en_fazla_gun=62):
    """Grafik icin gun gun ciro. Uzun araliklarda son gunler gosterilir."""
    from kahve.models import KahveSatis

    from .models import Satis

    if (bitis - baslangic).days >= en_fazla_gun:
        baslangic = bitis - timedelta(days=en_fazla_gun - 1)

    gunler = {}
    gun = baslangic
    while gun <= bitis:
        gunler[gun] = {"kirtasiye": Decimal("0.00"), "kahve": Decimal("0.00")}
        gun += timedelta(days=1)

    for model, anahtar in ((Satis, "kirtasiye"), (KahveSatis, "kahve")):
        sorgu = (
            model.objects.filter(tarih__date__gte=baslangic, tarih__date__lte=bitis)
            .values("tarih__date")
            .annotate(ciro=Sum("toplam"))
        )
        for satir in sorgu:
            hedef = gunler.get(satir["tarih__date"])
            if hedef is not None:
                hedef[anahtar] = _sifirdan(satir["ciro"])

    return [
        {"gun": gun, "kirtasiye": deger["kirtasiye"], "kahve": deger["kahve"],
         "toplam": deger["kirtasiye"] + deger["kahve"]}
        for gun, deger in sorted(gunler.items())
    ]


def hareketler(baslangic, bitis, sinir=60):
    """Iki tezgahin satislari, tek listede, yeniden eskiye."""
    from kahve.models import KahveSatis

    from .models import Satis

    kayitlar = []
    for satis in (
        Satis.objects.filter(tarih__date__gte=baslangic, tarih__date__lte=bitis)
        .select_related("borc_musteri")
        .prefetch_related("satirlar")[:sinir]
    ):
        kayitlar.append({
            "tarih": satis.tarih,
            "tezgah": "Kırtasiye",
            "toplam": satis.toplam,
            "odeme": satis.get_odeme_turu_display(),
            "odeme_kodu": satis.odeme_turu,
            "kalem": satis.kalem_adedi,
            "musteri": satis.borc_musteri.isim_soyisim if satis.borc_musteri else "",
            "urunler": ", ".join(f"{s.miktar}x {s.urun_adi}" for s in satis.satirlar.all()[:6]),
        })
    for satis in (
        KahveSatis.objects.filter(tarih__date__gte=baslangic, tarih__date__lte=bitis)
        .select_related("borc_musteri", "musteri")[:sinir]
    ):
        kayitlar.append({
            "tarih": satis.tarih,
            "tezgah": "Kahve",
            "toplam": satis.toplam,
            "odeme": satis.get_odeme_turu_display(),
            "odeme_kodu": satis.odeme_turu,
            "kalem": satis.fincan_adedi,
            "musteri": (
                satis.borc_musteri.isim_soyisim if satis.borc_musteri
                else (satis.musteri.ad_soyad if satis.musteri else "")
            ),
            "urunler": satis.urunler,
        })
    kayitlar.sort(key=lambda k: k["tarih"], reverse=True)
    return kayitlar[:sinir]


def stok_hareketleri(baslangic, bitis, sinir=60):
    from .models import StokHareketi

    return list(
        StokHareketi.objects.filter(tarih__date__gte=baslangic, tarih__date__lte=bitis)
        .select_related("urun")[:sinir]
    )


def kritik_stok(esik=5, sinir=20):
    """Adedi girilmis ve esigin altina dusmus urunler."""
    from .models import Stok

    return list(
        Stok.objects.filter(stok_adedi__isnull=False, stok_adedi__lte=esik)
        .order_by("stok_adedi", "Urun_Adi")[:sinir]
    )
