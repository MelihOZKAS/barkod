"""Kirtasiye tezgahinda satisi tamamlama.

Onceden sepet sadece siliniyordu: ne satildigi, ne kadar nakit ne kadar kart
girdigi hicbir yerde yazmiyordu. Burasi o bosluğu dolduruyor.

Satis tek bir transaction icinde yazilir; yarim kalan satis ne stok dusurur
ne borc yazar.
"""

from decimal import Decimal

from django.db import transaction

from .models import BorcHareketi, Musteri, Satis, SatisSatiri, SepetUrun, StokHareketi


class SatisHatasi(Exception):
    """Kasiyere gosterilecek, beklenen hata."""


def sepet_ozeti(satirlar, en_fazla=8):
    """Sepeti "2x Defter, 1x Kalem" gibi tek satira dokur."""
    parcalar = [f"{s.miktar}x {s.urun.Urun_Adi}" for s in satirlar[:en_fazla]]
    kalan = len(satirlar) - en_fazla
    if kalan > 0:
        parcalar.append(f"+{kalan} ürün daha")
    return ", ".join(parcalar)


def _para(deger):
    try:
        return Decimal(str(deger).replace(",", ".")).quantize(Decimal("0.01"))
    except Exception:
        raise SatisHatasi("Tutar sayı olmalı.")


@transaction.atomic
def satisi_tamamla(kullanici, odeme_turu, nakit=None, kart=None,
                   borc_musteri_id=None, not_metni="", borc_tutar=None,
                   indirim_tutari=None):
    satirlar = list(
        SepetUrun.objects.filter(user=kullanici).select_related("urun")
    )
    if not satirlar:
        raise SatisHatasi("Sepet boş.")

    gecerli = {c[0] for c in Satis.Odeme.choices}
    if odeme_turu not in gecerli:
        raise SatisHatasi("Ödeme türü geçersiz.")

    ara_toplam = sum((s.urun.Tutar * s.miktar for s in satirlar), Decimal("0.00"))
    ara_toplam = ara_toplam.quantize(Decimal("0.01"))

    # Indirim sepetin tamamina uygulanir; kasaya giren para indirimli tutar.
    indirim = _para(indirim_tutari or 0)
    if indirim < 0:
        raise SatisHatasi("İndirim eksi olamaz.")
    if indirim > ara_toplam:
        raise SatisHatasi("İndirim sepet toplamından büyük olamaz.")
    toplam = ara_toplam - indirim

    borc_musteri = None
    if odeme_turu == Satis.Odeme.NAKIT:
        nakit_tutar, kart_tutar = toplam, Decimal("0.00")
    elif odeme_turu == Satis.Odeme.KART:
        nakit_tutar, kart_tutar = Decimal("0.00"), toplam
    elif odeme_turu == Satis.Odeme.BORC:
        borc_musteri = Musteri.objects.filter(pk=borc_musteri_id).first()
        if borc_musteri is None:
            raise SatisHatasi("Borç yazılacak müşteriyi seçin.")
        # Parcali aktarma: tutarin bir kismi borca, kalani kasaya nakit.
        yazilan = toplam if borc_tutar is None else _para(borc_tutar)
        if yazilan <= 0:
            raise SatisHatasi("Borca yazılacak tutar 0'dan büyük olmalı.")
        if yazilan > toplam:
            raise SatisHatasi("Borç tutarı sepet toplamından büyük olamaz.")
        nakit_tutar, kart_tutar = toplam - yazilan, Decimal("0.00")
    else:
        nakit_tutar, kart_tutar = _para(nakit or 0), _para(kart or 0)
        if nakit_tutar < 0 or kart_tutar < 0:
            raise SatisHatasi("Tutarlar eksi olamaz.")
        if nakit_tutar + kart_tutar != toplam:
            raise SatisHatasi(
                f"Nakit + kart toplamı {toplam} ₺ olmalı "
                f"(şu an {nakit_tutar + kart_tutar} ₺)."
            )

    satis = Satis.objects.create(
        toplam=toplam,
        indirim_tutari=indirim,
        nakit_tutar=nakit_tutar,
        kart_tutar=kart_tutar,
        borc_tutar=(toplam - nakit_tutar - kart_tutar),
        odeme_turu=odeme_turu,
        borc_musteri=borc_musteri,
        kalem_adedi=sum(s.miktar for s in satirlar),
        kasiyer=kullanici.get_username(),
        notlar=not_metni,
    )

    for satir in satirlar:
        urun = satir.urun
        SatisSatiri.objects.create(
            satis=satis,
            urun=urun,
            urun_adi=urun.Urun_Adi,
            birim_fiyat=urun.Tutar or Decimal("0.00"),
            miktar=satir.miktar,
        )
        # Adedi bos olan urun takip edilmiyor; ona dokunma.
        if urun.stok_adedi is not None:
            onceki = urun.stok_adedi
            urun.stok_adedi = onceki - satir.miktar
            urun.save(update_fields=["stok_adedi"])
            StokHareketi.objects.create(
                urun=urun,
                tur=StokHareketi.Tur.SATIS,
                miktar=-satir.miktar,
                onceki_adet=onceki,
                sonraki_adet=urun.stok_adedi,
                aciklama=f"Satış #{satis.id}",
                kullanici=satis.kasiyer,
            )

    if borc_musteri is not None:
        metin = ["Kırtasiye satışı borça aktarıldı."]
        alinanlar = sepet_ozeti(satirlar)
        if alinanlar:
            metin.append(f"Alınanlar: {alinanlar}")
        if indirim:
            metin.append(f"İndirim: {indirim:.2f} ₺ (ara toplam {ara_toplam:.2f} ₺)")
        if not_metni:
            metin.append(f"Not: {not_metni}")
        if satis.nakit_tutar:
            metin.append(
                f"Parçalı: sepet {toplam:.2f} ₺, borca {satis.borc_tutar:.2f} ₺, "
                f"kasaya {satis.nakit_tutar:.2f} ₺."
            )
        onceki_borc = borc_musteri.borc
        borc_musteri.borc += satis.borc_tutar
        borc_musteri.save(update_fields=["borc"])
        BorcHareketi.objects.create(
            musteri=borc_musteri,
            tutar=satis.borc_tutar,
            aciklama="\n".join(metin),
            onceki_borc=onceki_borc,
        )

    SepetUrun.objects.filter(user=kullanici).delete()
    return satis
