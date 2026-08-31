"""Kasadaki ozel indirim.

Bazi musterilere elle indirim veriliyor. Indirim SEPETIN tamamina uygulanir,
oturumda tutulur ve satis bitince temizlenir - yarim kalan bir satis bir
sonraki musteriye indirim tasimasin.

Oturumdaki bicim:
    {"tur": "tl" | "yuzde", "deger": "10.00"}
"""

from decimal import Decimal, InvalidOperation

ANAHTAR = "stok_sepet_indirimi"


class IndirimHatasi(Exception):
    """Kasiyere gosterilecek, beklenen hata."""


def _para(deger):
    try:
        return Decimal(str(deger).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise IndirimHatasi("İndirim sayı olmalı.")


def oku(request):
    veri = request.session.get(ANAHTAR)
    if not isinstance(veri, dict) or veri.get("tur") not in ("tl", "yuzde"):
        return None
    return veri


def yaz(request, tur, deger):
    if tur not in ("tl", "yuzde"):
        raise IndirimHatasi("İndirim türü geçersiz.")
    tutar = _para(deger)
    if tutar < 0:
        raise IndirimHatasi("İndirim eksi olamaz.")
    if tur == "yuzde" and tutar > 100:
        raise IndirimHatasi("Yüzde 100'den büyük olamaz.")
    if tutar == 0:
        temizle(request)
        return None
    request.session[ANAHTAR] = {"tur": tur, "deger": str(tutar)}
    return request.session[ANAHTAR]


def temizle(request):
    request.session.pop(ANAHTAR, None)


def hesapla(ara_toplam, veri):
    """Indirim tutarini dondurur. Ara toplami asamaz, eksiye dusuremez."""
    if not veri:
        return Decimal("0.00")
    deger = _para(veri["deger"])
    if veri["tur"] == "yuzde":
        tutar = (ara_toplam * deger / Decimal("100")).quantize(Decimal("0.01"))
    else:
        tutar = deger
    return min(max(tutar, Decimal("0.00")), ara_toplam)


def ozet(request, ara_toplam):
    """Sablon ve JSON icin: ara toplam, indirim, odenecek."""
    veri = oku(request)
    tutar = hesapla(ara_toplam, veri)
    return {
        "var": bool(veri) and tutar > 0,
        "tur": veri["tur"] if veri else "tl",
        "deger": veri["deger"] if veri else "",
        "tutar": tutar,
        "ara_toplam": ara_toplam,
        "odenecek": ara_toplam - tutar,
    }
