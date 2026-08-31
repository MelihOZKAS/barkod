"""Kasa sepeti.

Sepet oturumda (session) tutulur: sayfa yenilense de kaybolmaz, ama
satis tamamlanmadan veritabanina hicbir sey yazilmaz.

Oturumdaki bicim:
    {"satirlar": [{"kahve_id": 3, "adet": 2, "hediye_adet": 1}], "musteri_id": 7}
"""

from decimal import Decimal

from django.db import transaction

from stok import indirim as indirim_modulu
from stok.models import BorcHareketi, Musteri

from . import sadakat
from .models import Kahve, KahveAyar, KahveMusteri, KahveSatis

SEPET_ANAHTARI = "kahve_kasa_sepeti"


def _bos_sepet():
    return {"satirlar": [], "musteri_id": None}


def _sepeti_oku(request):
    sepet = request.session.get(SEPET_ANAHTARI)
    if not isinstance(sepet, dict) or "satirlar" not in sepet:
        sepet = _bos_sepet()
    return sepet


def _sepeti_yaz(request, sepet):
    request.session[SEPET_ANAHTARI] = sepet
    request.session.modified = True


def _satir_bul(sepet, kahve_id):
    for satir in sepet["satirlar"]:
        if satir["kahve_id"] == kahve_id:
            return satir
    return None


# ---------------------------------------------------------------------------
# Sepet islemleri
# ---------------------------------------------------------------------------

def sepete_ekle(request, kahve_id, adet=1):
    sepet = _sepeti_oku(request)
    satir = _satir_bul(sepet, kahve_id)
    if satir is None:
        sepet["satirlar"].append({"kahve_id": kahve_id, "adet": adet, "hediye_adet": 0})
    else:
        satir["adet"] += adet
    _sepeti_yaz(request, sepet)
    return sepet


def adet_degistir(request, kahve_id, adet):
    sepet = _sepeti_oku(request)
    satir = _satir_bul(sepet, kahve_id)
    if satir is None:
        return sepet
    if adet < 1:
        sepet["satirlar"].remove(satir)
    else:
        satir["adet"] = adet
        satir["hediye_adet"] = min(satir["hediye_adet"], adet)
    _sepeti_yaz(request, sepet)
    return sepet


def satir_sil(request, kahve_id):
    sepet = _sepeti_oku(request)
    satir = _satir_bul(sepet, kahve_id)
    if satir is not None:
        sepet["satirlar"].remove(satir)
        _sepeti_yaz(request, sepet)
    return sepet


def indirimi_temizle(request):
    """Kasa sifirlaninca indirim de gitsin; bir sonraki musteriye tasinmasin."""
    indirim_modulu.temizle(request, indirim_modulu.KAHVE_ANAHTAR)


def sepeti_temizle(request, musteriyi_de=True):
    sepet = _sepeti_oku(request)
    sepet["satirlar"] = []
    if musteriyi_de:
        sepet["musteri_id"] = None
    _sepeti_yaz(request, sepet)
    return sepet


def musteri_bagla(request, musteri):
    sepet = _sepeti_oku(request)
    sepet["musteri_id"] = musteri.id if musteri else None
    if musteri is None:
        for satir in sepet["satirlar"]:
            satir["hediye_adet"] = 0
    _sepeti_yaz(request, sepet)
    return sepet


def hediye_degistir(request, kahve_id, hediye_adet):
    """Bir satirin kac fincanini hediyeyle karsilayacagimizi belirler."""
    sepet = _sepeti_oku(request)
    satir = _satir_bul(sepet, kahve_id)
    if satir is None:
        return sepet

    musteri = _musteri(sepet)
    kahve = Kahve.objects.filter(pk=kahve_id).first()
    if musteri is None or kahve is None or not kahve.hediye_gecerli:
        satir["hediye_adet"] = 0
        _sepeti_yaz(request, sepet)
        return sepet

    # Sepetteki diger satirlarin kullandigi hediyeler dusulur.
    baskalarinin = sum(
        s["hediye_adet"] for s in sepet["satirlar"] if s["kahve_id"] != kahve_id
    )
    kalan_hediye = max(0, musteri.bekleyen_hediye_sayisi - baskalarinin)

    satir["hediye_adet"] = max(0, min(hediye_adet, satir["adet"], kalan_hediye))
    _sepeti_yaz(request, sepet)
    return sepet


def _musteri(sepet):
    if not sepet.get("musteri_id"):
        return None
    return KahveMusteri.objects.filter(pk=sepet["musteri_id"], aktif=True).first()


# ---------------------------------------------------------------------------
# Ekranin okudugu tek kaynak
# ---------------------------------------------------------------------------

def indirim_ozeti(request, ara_toplam):
    """Kahve sepetindeki indirim. Kirtasiyeden ayri oturum kutusu kullanir."""
    return indirim_modulu.ozet(request, ara_toplam, indirim_modulu.KAHVE_ANAHTAR)


def ozet(request):
    sepet = _sepeti_oku(request)
    musteri = _musteri(sepet)

    kahveler = {k.id: k for k in Kahve.objects.filter(pk__in=[s["kahve_id"] for s in sepet["satirlar"]])}

    satirlar = []
    toplam = Decimal("0.00")
    fincan = 0
    hediye = 0
    damga = 0

    # Silinmis kahveleri sepetten dusur
    sepet["satirlar"] = [s for s in sepet["satirlar"] if s["kahve_id"] in kahveler]

    for satir in sepet["satirlar"]:
        kahve = kahveler[satir["kahve_id"]]
        adet = satir["adet"]
        hediye_adet = satir["hediye_adet"] if musteri else 0
        odenecek = adet - hediye_adet
        ara_toplam = kahve.fiyat * odenecek

        toplam += ara_toplam
        fincan += adet
        hediye += hediye_adet
        if kahve.damga_veriyor:
            # Hediyeyle alinan fincan yeni damga vermez.
            damga += adet - hediye_adet

        satirlar.append({
            "kahve_id": kahve.id,
            "ad": kahve.ad,
            "fiyat": float(kahve.fiyat),
            "adet": adet,
            "hediye_adet": hediye_adet,
            "hediye_gecerli": kahve.hediye_gecerli,
            "damga_veriyor": kahve.damga_veriyor,
            "ara_toplam": float(ara_toplam),
        })

    _sepeti_yaz(request, sepet)

    # Indirim hediyeler dusuldukten SONRAKI tutara uygulanir; bedava verilen
    # fincandan ayrica indirim yapmanin anlami yok.
    ind = indirim_ozeti(request, toplam)

    veri = {
        "satirlar": satirlar,
        "ara_toplam": float(toplam),
        "indirim": float(ind["tutar"]),
        "indirim_tur": ind["tur"],
        "indirim_deger": ind["deger"],
        "indirim_var": ind["var"],
        # toplam = odenecek tutar. Odeme dogrulamalari ve satis bunu kullaniyor.
        "toplam": float(ind["odenecek"]),
        "fincan_adedi": fincan,
        "hediye_adedi": hediye,
        "damga_adedi": damga,
        "musteri": None,
    }

    if musteri:
        durum = sadakat.kart_durumu(musteri)
        veri["musteri"] = {
            "id": musteri.id,
            "ad_soyad": musteri.ad_soyad,
            "kod": musteri.kod,
            "aktif_kahve": durum["aktif_sayi"],
            "esik": durum["esik"],
            "kalan": durum["kalan"],
            "bekleyen_hediye": durum["bekleyen_hediye"],
            "kullanilabilir_hediye": max(0, durum["bekleyen_hediye"] - hediye),
            "damgalar": [
                {"dolu": d["dolu"], "sonuyor": d["sonuyor"], "kalan_gun": d["kalan_gun"]}
                for d in durum["damgalar"]
            ],
        }
    return veri


# ---------------------------------------------------------------------------
# Satisi tamamla
# ---------------------------------------------------------------------------

class SatisHatasi(Exception):
    pass


@transaction.atomic
def satis_ozeti(satirlar, en_fazla=8):
    """Satisi "2x Latte, 1x Espresso" gibi tek satira dokur.

    Borc hareketinin aciklamasina giriyor: musteri "ne almistim?" diye
    sordugunda cevap kayitta dursun.
    """
    parcalar = [f"{s['adet']}x {s['ad']}" for s in satirlar[:en_fazla]]
    kalan = len(satirlar) - en_fazla
    if kalan > 0:
        parcalar.append(f"+{kalan} ürün daha")
    return ", ".join(parcalar)


def satisi_tamamla(request, odeme_turu, nakit=None, kart=None, kasiyer="",
                   borc_musteri_id=None, not_metni=""):
    veri = ozet(request)
    if not veri["satirlar"]:
        raise SatisHatasi("Sepet boş.")

    toplam = Decimal(str(veri["toplam"]))          # indirim dusulmus
    indirim = Decimal(str(veri["indirim"]))
    gecerli = {c[0] for c in KahveSatis.Odeme.choices}
    if odeme_turu not in gecerli:
        raise SatisHatasi("Ödeme türü geçersiz.")

    borc_musteri = None
    if odeme_turu == KahveSatis.Odeme.BORC:
        if toplam <= 0:
            raise SatisHatasi("Tutar 0 olan satış borca yazılmaz.")
        borc_musteri = Musteri.objects.filter(pk=borc_musteri_id).first()
        if borc_musteri is None:
            raise SatisHatasi("Borç yazılacak müşteriyi seçin.")

    if odeme_turu == KahveSatis.Odeme.NAKIT:
        nakit_tutar, kart_tutar = toplam, Decimal("0.00")
    elif odeme_turu == KahveSatis.Odeme.KART:
        nakit_tutar, kart_tutar = Decimal("0.00"), toplam
    elif odeme_turu == KahveSatis.Odeme.BORC:
        # Kasaya para girmedi; tutar musterinin borcuna yazildi.
        nakit_tutar, kart_tutar = Decimal("0.00"), Decimal("0.00")
    else:
        try:
            nakit_tutar = Decimal(str(nakit or 0)).quantize(Decimal("0.01"))
            kart_tutar = Decimal(str(kart or 0)).quantize(Decimal("0.01"))
        except Exception:
            raise SatisHatasi("Parçalı tutarlar sayı olmalı.")
        if nakit_tutar < 0 or kart_tutar < 0:
            raise SatisHatasi("Tutarlar eksi olamaz.")
        if nakit_tutar + kart_tutar != toplam:
            raise SatisHatasi(
                f"Nakit + kart toplamı {toplam} TL olmalı "
                f"(şu an {nakit_tutar + kart_tutar} TL)."
            )

    sepet = _sepeti_oku(request)
    musteri = _musteri(sepet)

    satis = KahveSatis.objects.create(
        musteri=musteri,
        borc_musteri=borc_musteri,
        toplam=toplam,
        indirim_tutari=indirim,
        nakit_tutar=nakit_tutar,
        kart_tutar=kart_tutar,
        odeme_turu=odeme_turu,
        urunler=satis_ozeti(veri["satirlar"])[:255],
        fincan_adedi=veri["fincan_adedi"],
        hediye_adedi=veri["hediye_adedi"] if musteri else 0,
        kasiyer=kasiyer,
    )

    if borc_musteri is not None:
        satirlar_metni = ["Kahve satışı borça aktarıldı."]
        alinanlar = satis_ozeti(veri["satirlar"])
        if alinanlar:
            satirlar_metni.append(f"Alınanlar: {alinanlar}")
        if indirim:
            satirlar_metni.append(
                f"İndirim: {indirim:.2f} ₺ (ara toplam {toplam + indirim:.2f} ₺)"
            )
        if not_metni:
            satirlar_metni.append(f"Not: {not_metni}")
        onceki_borc = borc_musteri.borc
        borc_musteri.borc += toplam
        borc_musteri.save(update_fields=["borc"])
        BorcHareketi.objects.create(
            musteri=borc_musteri,
            tutar=toplam,
            aciklama="\n".join(satirlar_metni),
            onceki_borc=onceki_borc,
        )

    kazanilan = 0
    if musteri:
        for satir in veri["satirlar"]:
            kahve = Kahve.objects.get(pk=satir["kahve_id"])
            for _ in range(satir["hediye_adet"]):
                if sadakat.hediye_kullan(musteri, kahve, ekleyen=kasiyer, satis=satis) is None:
                    raise SatisHatasi("Hediye kahve bu arada kullanılmış, sepeti yenileyin.")
            for _ in range(satir["adet"] - satir["hediye_adet"]):
                sonuc = sadakat.kahve_ekle(musteri, kahve, ekleyen=kasiyer, satis=satis)
                kazanilan += len(sonuc["kazanilan_hediyeler"])

    sepeti_temizle(request)  # satis bitti, kasa sifirlanir
    indirim_modulu.temizle(request, indirim_modulu.KAHVE_ANAHTAR)
    return {"satis": satis, "kazanilan_hediye": kazanilan}


def gunun_ozeti(kasiyer=None):
    """Kasa ekraninin altinda gosterilen gunluk toplam."""
    from django.db.models import Count, Q, Sum
    from django.utils import timezone

    bugun = timezone.localtime().date()
    qs = KahveSatis.objects.filter(tarih__date=bugun)
    toplamlar = qs.aggregate(
        ciro=Sum("toplam"), nakit=Sum("nakit_tutar"), kart=Sum("kart_tutar"),
        # Borca yazilan tutar kasaya girmedi; ayri gosterilmeli.
        borc=Sum("toplam", filter=Q(odeme_turu=KahveSatis.Odeme.BORC)),
        indirim=Sum("indirim_tutari"),
        fincan=Sum("fincan_adedi"), satis=Count("id"),
    )
    return {anahtar: (deger or 0) for anahtar, deger in toplamlar.items()}
