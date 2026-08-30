"""Sadakat kurallari.

Kural: musteri her kahve ictiginde bir "icim" kaydi acilir ve o kayit
`gecerlilik_gun` kadar sayacta durur. Sayacta `hediye_icin_kahve` adet
birikince en eski kahvelerden o kadari harcanir ve 1 hediye kahve yazilir.
Sayacta bekleyen bir kahvenin suresi dolarsa sayactan duser (5 -> 4).

Sure kontrolu iki yerden calisir:
  1. Her gece cron ile tum musteriler icin (bkz. views.cron_temizlik)
  2. Musterinin karti/kasada okundugu anda sadece o musteri icin
Boylece cron bir gun calismasa bile ekranda gorunen sayi dogru kalir.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import HediyeKahve, KahveAyar, KahveIcim, KahveMusteri


def suresi_dolanlari_dusur(musteri=None, simdi=None):
    """Suresi gecmis kahveleri sayactan dusurur. Dusen kahve adedini dondurur."""
    simdi = simdi or timezone.now()
    qs = KahveIcim.objects.filter(
        durum=KahveIcim.Durum.AKTIF,
        son_gecerlilik__isnull=False,
        son_gecerlilik__lte=simdi,
    )
    if musteri is not None:
        qs = qs.filter(musteri=musteri)
    return qs.update(durum=KahveIcim.Durum.DOLDU)


def _hediyeleri_hesapla(musteri, ayar):
    """Sayac esigi gectiyse en eski kahveleri harcayip hediye yazar."""
    esik = max(1, ayar.hediye_icin_kahve)
    kazanilan = []
    while True:
        aktifler = list(musteri.aktif_icimler()[:esik])
        if len(aktifler) < esik:
            break
        KahveIcim.objects.filter(pk__in=[i.pk for i in aktifler]).update(durum=KahveIcim.Durum.HARCANDI)
        kazanilan.append(HediyeKahve.objects.create(musteri=musteri))
    return kazanilan


@transaction.atomic
def kahve_ekle(musteri, kahve=None, ekleyen="", tarih=None, satis=None):
    """Musteriye bir kahve yazar. {'icim':..., 'kazanilan_hediyeler':[...]} doner."""
    ayar = KahveAyar.al()
    tarih = tarih or timezone.now()
    suresi_dolanlari_dusur(musteri=musteri, simdi=tarih)

    # Urun sayaca girmiyorsa (kurabiye, su...) kayit yine acilir ama damga saymaz.
    # Elle yazilan kahvede (kahve=None) damga verilir.
    damga_verir = kahve is None or kahve.damga_veriyor

    icim = KahveIcim.objects.create(
        musteri=musteri,
        kahve=kahve,
        kahve_adi=kahve.ad if kahve else "Kahve",
        fiyat=kahve.fiyat if kahve else 0,
        durum=KahveIcim.Durum.AKTIF if damga_verir else KahveIcim.Durum.SAYILMAZ,
        tarih=tarih,
        son_gecerlilik=tarih + timedelta(days=ayar.gecerlilik_gun) if damga_verir else None,
        ekleyen=ekleyen,
        satis=satis,
    )
    kazanilan = _hediyeleri_hesapla(musteri, ayar) if damga_verir else []
    KahveMusteri.objects.filter(pk=musteri.pk).update(son_gorulme=tarih)
    return {"icim": icim, "kazanilan_hediyeler": kazanilan}


@transaction.atomic
def hediye_kullan(musteri, kahve=None, ekleyen="", satis=None):
    """Bekleyen bir hediyeyi harcar. Hediye yoksa None doner."""
    hediye = (
        HediyeKahve.objects.select_for_update()
        .filter(musteri=musteri, durum=HediyeKahve.Durum.BEKLIYOR)
        .order_by("kazanma_tarihi")
        .first()
    )
    if hediye is None:
        return None

    simdi = timezone.now()
    icim = KahveIcim.objects.create(
        musteri=musteri,
        kahve=kahve,
        kahve_adi=kahve.ad if kahve else "Hediye kahve",
        fiyat=0,
        durum=KahveIcim.Durum.HEDIYE,  # hediye kahve yeni sayaca eklenmez
        tarih=simdi,
        son_gecerlilik=None,
        ekleyen=ekleyen,
        satis=satis,
    )
    hediye.durum = HediyeKahve.Durum.KULLANILDI
    hediye.kullanma_tarihi = simdi
    hediye.kullanilan_icim = icim
    hediye.save(update_fields=["durum", "kullanma_tarihi", "kullanilan_icim"])
    KahveMusteri.objects.filter(pk=musteri.pk).update(son_gorulme=simdi)
    return {"hediye": hediye, "icim": icim}


def kart_durumu(musteri, temizle=True):
    """Kart ekraninin ve mobil API'nin kullandigi tek kaynak."""
    ayar = KahveAyar.al()
    if temizle:
        suresi_dolanlari_dusur(musteri=musteri)
        _hediyeleri_hesapla(musteri, ayar)

    esik = max(1, ayar.hediye_icin_kahve)
    aktifler = list(musteri.aktif_icimler())
    damgalar = []
    for sira in range(esik):
        icim = aktifler[sira] if sira < len(aktifler) else None
        kalan_gun = icim.kalan_gun if icim else None
        damgalar.append(
            {
                "sira": sira + 1,
                "dolu": icim is not None,
                "icim": icim,
                "tarih": icim.tarih if icim else None,
                "kalan_gun": kalan_gun,
                "sonuyor": kalan_gun is not None and kalan_gun <= 3,
                "kahve_adi": icim.kahve_adi if icim else "",
            }
        )

    return {
        "ayar": ayar,
        "musteri": musteri,
        "esik": esik,
        "aktif_sayi": len(aktifler),
        "kalan": max(0, esik - len(aktifler)),
        "damgalar": damgalar,
        "bekleyen_hediye": musteri.bekleyen_hediye_sayisi,
        "toplam_icim": musteri.toplam_icim_sayisi,
        "en_yakin_dusen": aktifler[0] if aktifler else None,
    }
