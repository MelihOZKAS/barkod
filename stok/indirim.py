"""Kasadaki ozel indirim. Iki tezgah da bunu kullaniyor.

Bazi musterilere elle indirim veriliyor. Indirim SEPETIN tamamina uygulanir,
oturumda tutulur ve satis bitince temizlenir - yarim kalan bir satis bir
sonraki musteriye indirim tasimasin.

Iki tezgahin sepeti ayri oldugu icin oturum anahtari da ayri: kirtasiyede
ANAHTAR, kahvede KAHVE_ANAHTAR. Ayni fonksiyonlar, farkli kutu.

Oturumdaki bicim:
    {"tur": "tl" | "yuzde", "deger": "10.00"}
"""

from decimal import Decimal, InvalidOperation

ANAHTAR = "stok_sepet_indirimi"
KAHVE_ANAHTAR = "kahve_sepet_indirimi"


class IndirimHatasi(Exception):
    """Kasiyere gosterilecek, beklenen hata."""


def _para(deger):
    try:
        return Decimal(str(deger).replace(",", ".")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        raise IndirimHatasi("İndirim sayı olmalı.")


def oku(request, anahtar=ANAHTAR):
    veri = request.session.get(anahtar)
    if not isinstance(veri, dict) or veri.get("tur") not in ("tl", "yuzde"):
        return None
    return veri


def yaz(request, tur, deger, anahtar=ANAHTAR):
    if tur not in ("tl", "yuzde"):
        raise IndirimHatasi("İndirim türü geçersiz.")
    tutar = _para(deger)
    if tutar < 0:
        raise IndirimHatasi("İndirim eksi olamaz.")
    if tur == "yuzde" and tutar > 100:
        raise IndirimHatasi("Yüzde 100'den büyük olamaz.")
    if tutar == 0:
        temizle(request, anahtar)
        return None
    request.session[anahtar] = {"tur": tur, "deger": str(tutar)}
    return request.session[anahtar]


def temizle(request, anahtar=ANAHTAR):
    request.session.pop(anahtar, None)


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


def ozet(request, ara_toplam, anahtar=ANAHTAR):
    """Sablon ve JSON icin: ara toplam, indirim, odenecek."""
    veri = oku(request, anahtar)
    tutar = hesapla(ara_toplam, veri)
    return {
        "var": bool(veri) and tutar > 0,
        "tur": veri["tur"] if veri else "tl",
        "deger": veri["deger"] if veri else "",
        "tutar": tutar,
        "ara_toplam": ara_toplam,
        "odenecek": ara_toplam - tutar,
    }
