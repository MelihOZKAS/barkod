"""Raf etiketi: hangi urunler, hangi olcu, kac kopya.

Etiketin kendisi templates/system/user/etiket.html icinde; burada sadece
sayfaya ne gonderilecegi hesaplaniyor. Barkod cizimi stok/barkod.py'de.

Secim iki yoldan gelir:
  * admin'deki "raf etiketi yazdir" eylemi -> id'ler OTURUM_ANAHTARI ile
    oturuma yazilir, sayfa oradan okur. Binlerce urun secilse bile URL
    uzunlugu sorun olmaz, sayfa yenilenince secim kaybolmaz.
  * dogrudan baglanti -> ?ids=12,13  ya da  ?q=defter
"""

import math
from collections import Counter

from .barkod import barkod_ciz
from .models import Stok

OTURUM_ANAHTARI = "etiket_urunleri"

# A4'un basilabilir alani 6 mm kenar bosluguyla 198 x 285 mm. Olculer o alana
# tam sigacak sekilde secildi; satir sayisi asagi yuvarlandi ki son satir
# yazicinin basamadigi kenara tasmasin.
OLCULER = {
    # Dukkandaki Xprinter XP-470B termal etiket yazicisinin rulosu. Varsayilan
    # olcu bu: gunluk is bu yazicidan cikiyor, A4 olculeri yedek.
    "termal": {
        "ad": "Etiket yazıcısı",
        "aciklama": "95 × 39 mm rulo · Xprinter XP-470B",
        "genislik": 95.0, "yukseklik": 39.0, "sutun": 2, "satir": 7,
        "dar": False,
    },
    "kucuk": {
        "ad": "Küçük",
        "aciklama": "49,5 × 30 mm · A4'e 36 etiket",
        "genislik": 49.5, "yukseklik": 30.0, "sutun": 4, "satir": 9,
        "dar": True,
    },
    "orta": {
        "ad": "Orta",
        "aciklama": "66 × 40 mm · A4'e 21 etiket",
        "genislik": 66.0, "yukseklik": 40.0, "sutun": 3, "satir": 7,
        "dar": False,
    },
    "buyuk": {
        "ad": "Büyük",
        "aciklama": "99 × 57 mm · A4'e 10 etiket",
        "genislik": 99.0, "yukseklik": 57.0, "sutun": 2, "satir": 5,
        "dar": False,
    },
}
VARSAYILAN_OLCU = "termal"

# Sayfa duzeni. "tek" secilince kagit boyu etiketin kendisi olur: etiket
# yazicisinin rulosuna ya da tek tek beslenen etiket kagidina basmak icin.
DUZENLER = {
    "sayfa": "A4 sayfaya sığdır",
    "tek": "Tek tek — her etiket ayrı sayfa",
}
VARSAYILAN_DUZEN = "tek"

EN_COK_URUN = 600      # tek seferde basilacak urun sayisi
EN_COK_KOPYA = 50      # urun basina kopya

# Termal yazicilar etiketi her zaman ayni noktadan baslatmiyor (bosluk sensoru
# kalibrasyonu, rulonun gerginligi). Kullanici basilan seyi milim milim
# kaydirabilsin diye; 20 mm'den fazlasi zaten baska bir arizadir.
EN_COK_KAYDIRMA = 20.0

# Sinama etiketindeki cetvel araligi.
CETVEL_ARALIGI = 5

# Sinama kac etiket bassin. Tek etiket kaymayi gosteriyor ama "yazicinin sayfa
# boyu etiketin boyuyla ayni mi" sorusunu cevaplamiyor: ard arda uc numarali
# etiket basilinca arada bos etiket kalip kalmadigi tek bakista goruluyor.
SINAMA_ETIKET_SAYISI = 3


def _sayi(deger, varsayilan, en_az, en_cok):
    try:
        sonuc = int(deger)
    except (TypeError, ValueError):
        return varsayilan
    return max(en_az, min(en_cok, sonuc))


def _ondalik(deger, varsayilan, en_az, en_cok):
    """Milim cinsinden kaydirma. Virgullu yazilirsa da kabul edilir."""
    try:
        sonuc = float(str(deger).replace(",", "."))
    except (TypeError, ValueError):
        return varsayilan
    if not math.isfinite(sonuc):
        return varsayilan
    return max(en_az, min(en_cok, round(sonuc, 2)))


def _cetvel(uzunluk):
    """Sinama etiketindeki cetvel isaretleri: 0'dan kenara kadar 5 mm'de bir."""
    return list(range(0, int(uzunluk) + 1, CETVEL_ARALIGI))


def secilen_urunler(istek):
    """Etiketi basilacak urunler. Sirasi: ?ids= > ?q= > oturumdaki secim."""
    ham_ids = (istek.GET.get("ids") or "").strip()
    if ham_ids:
        idler = [int(p) for p in ham_ids.replace(" ", "").split(",") if p.isdigit()]
    elif (istek.GET.get("q") or "").strip():
        arama = istek.GET["q"].strip()
        return list(
            Stok.objects.filter(Urun_Genel__icontains=arama).order_by("Urun_Adi")[:EN_COK_URUN]
        )
    else:
        idler = istek.session.get(OTURUM_ANAHTARI) or []

    if not idler:
        return []
    idler = idler[:EN_COK_URUN]
    bulunan = {u.id: u for u in Stok.objects.filter(id__in=idler)}
    # Gelen sirayi koru: admin'de neye gore siralandiysa etiketler de oyle ciksin.
    return [bulunan[i] for i in idler if i in bulunan]


def etiket_verisi(urun):
    cizim = barkod_ciz(urun.Barkod)
    return {
        "urun": urun,
        "barkod_svg": cizim.svg if cizim else "",
        "barkod_metin": cizim.metin if cizim else str(urun.Barkod),
        "barkod_turu": cizim.tur if cizim else "",
        # Modul sayisi: barkodun genisligi bundan hesaplaniyor, boylece her
        # modul ayni milim genisliginde ciziliyor (bkz. --et-mw).
        "barkod_modul": cizim.genislik if cizim else 0,
        # F.D.T. once fiyat tarihinden, o hic yazilmamissa son guncellemeden.
        "fiyat_tarihi": urun.fiyat_tarihi or (
            urun.guncelleme_tarihi.date() if urun.guncelleme_tarihi else None
        ),
    }


def sayfa_baglami(istek):
    """Etiket sayfasinin tum baglami."""
    olcu_anahtari = istek.GET.get("boyut")
    if olcu_anahtari not in OLCULER:
        olcu_anahtari = VARSAYILAN_OLCU
    olcu = OLCULER[olcu_anahtari]

    duzen = istek.GET.get("duzen")
    if duzen not in DUZENLER:
        duzen = VARSAYILAN_DUZEN

    kopya = _sayi(istek.GET.get("kopya"), 1, 1, EN_COK_KOPYA)
    sayfada = 1 if duzen == "tek" else olcu["sutun"] * olcu["satir"]
    # Bastan bos birakmak sadece A4 dizilisinde anlamli: yarim kalmis etiket
    # sayfasi tekrar kullanilsin diye. Tek tek basarken diye bir sey yok.
    atla = 0 if duzen == "tek" else _sayi(istek.GET.get("atla"), 0, 0, sayfada - 1)

    # Sinama baskisi: urun etiketi yerine tek bir olcu etiketi cikar. Barkod
    # cizmeye gerek yok, 600 urun secili olsa bile bos yere ugrasmasin.
    sinama = istek.GET.get("sinama") == "1"

    urunler = secilen_urunler(istek)
    etiketler = []
    turler = Counter()
    if not sinama:
        for urun in urunler:
            veri = etiket_verisi(urun)
            turler[veri["barkod_turu"] or "Barkodsuz"] += 1
            # Ayni cizim kopya sayisi kadar tekrarlanir; barkod bir kez uretilir.
            etiketler.extend([veri] * kopya)

    return {
        "etiketler": etiketler,
        "urun_sayisi": len(urunler),
        "bos_yerler": range(atla),
        "olcu": olcu,
        "olcu_anahtari": olcu_anahtari,
        "olculer": OLCULER,
        "duzen": duzen,
        "duzenler": DUZENLER,
        "kopya": kopya,
        "atla": atla,
        "sayfada": sayfada,
        # Varsayilan beyaz: termal kafa bos yere yanmasin, baski hizlansin.
        # Isteyen siyah serite gecebilir.
        "serit": istek.GET.get("serit", "0") != "0",
        # Rulo etiketi zaten kesilmis geliyor; kesim cizgisi sadece A4'te lazim.
        "kesim": istek.GET.get("kesim", "0" if duzen == "tek" else "1") != "0",
        # Yazicinin kagidi kacirdigi durumda baskiyi elle kaydirmak icin.
        # CSS'e basildigi icin "%g": Turkce yerellestirmede {{ 1.5 }} "1,5"
        # yazilir, o da gecersiz bir CSS uzunlugu olur.
        "kay_x": "%g" % _ondalik(istek.GET.get("kx"), 0.0,
                                 -EN_COK_KAYDIRMA, EN_COK_KAYDIRMA),
        "kay_y": "%g" % _ondalik(istek.GET.get("ky"), 0.0,
                                 -EN_COK_KAYDIRMA, EN_COK_KAYDIRMA),
        "sinama": sinama,
        "sinama_liste": range(1, SINAMA_ETIKET_SAYISI + 1),
        # Hangi simgelemeden kac tane cikacak. Ekranda gorunur, kagida
        # basilmaz: kontrol hanesi tutmayan barkodlar Code 128'e dustugu icin
        # "hepsi Code 128" ciktisi barkod verisinde bir sorun oldugunu soyler.
        "barkod_ozeti": turler.most_common(),
        "cetvel_x": _cetvel(olcu["genislik"]),
        "cetvel_y": _cetvel(olcu["yukseklik"]),
        "arama": (istek.GET.get("q") or "").strip(),
        "ids": (istek.GET.get("ids") or "").strip(),
        "en_cok_urun": EN_COK_URUN,
    }
