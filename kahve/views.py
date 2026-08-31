import hmac
import json
from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from stok import indirim as indirim_modulu
from stok.models import Musteri

from . import kasa as kasa_sepeti
from . import sadakat
from .firebase import FirebaseHatasi, token_dogrula
from .models import Kahve, KahveAyar, KahveIcim, KahveKategori, KahveMusteri

MOBIL_BASLIK = "HTTP_X_KAHVE_KEY"


# --------------------------------------------------------------------------
# Yardimcilar
# --------------------------------------------------------------------------

def _esit_mi(a, b):
    return bool(a) and bool(b) and hmac.compare_digest(str(a), str(b))




def _govde(request):
    if request.content_type and "json" in request.content_type:
        try:
            return json.loads(request.body or b"{}")
        except ValueError:
            return {}
    return request.POST.dict()


def _musteri_ozet(musteri):
    durum = sadakat.kart_durumu(musteri)
    return {
        "id": musteri.id,
        "ad_soyad": musteri.ad_soyad,
        "email": musteri.email,
        "telefon": musteri.telefon,
        "kod": musteri.kod,
        "qr": str(musteri.qr_token),
        "aktif_kahve": durum["aktif_sayi"],
        "esik": durum["esik"],
        "kalan": durum["kalan"],
        "bekleyen_hediye": durum["bekleyen_hediye"],
        "toplam_icim": durum["toplam_icim"],
        "damgalar": [
            {
                "sira": d["sira"],
                "dolu": d["dolu"],
                "tarih": d["tarih"].isoformat() if d["tarih"] else None,
                "kalan_gun": d["kalan_gun"],
                "kahve_adi": d["kahve_adi"],
            }
            for d in durum["damgalar"]
        ],
    }


def _kategorilere_gore(kahveler):
    """[(kategori_adi, [kahve, ...]), ...] doner. Kategorisi olmayanlar en sonda."""
    gruplar, kategorisiz = [], []
    for kahve in kahveler:
        if kahve.kategori_id is None:
            kategorisiz.append(kahve)
            continue
        if gruplar and gruplar[-1][0] == kahve.kategori.ad:
            gruplar[-1][1].append(kahve)
        else:
            gruplar.append((kahve.kategori.ad, [kahve]))
    if kategorisiz:
        gruplar.append(("Diğer", kategorisiz))
    return gruplar


def _kahve_ozet(kahve, request=None):
    gorsel = ""
    if kahve.gorsel:
        gorsel = request.build_absolute_uri(kahve.gorsel.url) if request else kahve.gorsel.url
    return {
        "id": kahve.id,
        "ad": kahve.ad,
        "aciklama": kahve.aciklama,
        "icindekiler": kahve.icindekiler_listesi,
        "fiyat": float(kahve.fiyat),
        "gorsel": gorsel,
        "hediye_gecerli": kahve.hediye_gecerli,
        "damga_veriyor": kahve.damga_veriyor,
        "kategori": kahve.kategori.ad if kahve.kategori_id else "",
    }


def mobil_anahtar_gerekli(gorunum):
    """Mobil uygulama her istekte X-Kahve-Key basligini gondermek zorunda."""

    @wraps(gorunum)
    def sarmalayici(request, *args, **kwargs):
        gelen = request.META.get(MOBIL_BASLIK, "")
        if not _esit_mi(gelen, KahveAyar.al().mobil_api_anahtari):
            return JsonResponse({"ok": False, "hata": "Gecersiz uygulama anahtari."}, status=401)
        return gorunum(request, *args, **kwargs)

    return sarmalayici


def _bearer_musterisi(request):
    """Authorization: Bearer <firebase id token> -> KahveMusteri"""
    baslik = request.META.get("HTTP_AUTHORIZATION", "")
    if not baslik.lower().startswith("bearer "):
        return None, "Authorization basligi eksik."
    ayar = KahveAyar.al()
    try:
        bilgi = token_dogrula(baslik[7:].strip(), ayar.firebase_api_key)
    except FirebaseHatasi as hata:
        return None, str(hata)
    musteri = KahveMusteri.objects.filter(firebase_uid=bilgi["uid"], aktif=True).first()
    if musteri is None:
        return None, "Bu hesaba bagli musteri kaydi yok."
    return musteri, None


# --------------------------------------------------------------------------
# Web - halka acik menu
# Web'de musteri girisi YOK. Musteri hesaplari yalnizca mobil uygulamada
# (Firebase) yasar; buradaki sayfalar ya halka acik ya personele ozeldir.
# --------------------------------------------------------------------------

def menu(request):
    ayar = KahveAyar.al()
    return render(
        request,
        "kahve/menu.html",
        {
            "ayar": ayar,
            "gruplar": _kategorilere_gore(
                Kahve.objects.filter(aktif=True).select_related("kategori")
            ),
            "ornek_damgalar": range(max(1, ayar.hediye_icin_kahve)),
        },
    )


@staff_member_required
def kart_qr(request, token):
    """Personelin bir musterinin kartini gormesi icin. Admin'den link veriliyor."""
    musteri = get_object_or_404(KahveMusteri, qr_token=token, aktif=True)
    durum = sadakat.kart_durumu(musteri)
    durum["salt_okunur"] = True
    durum["gecmis"] = musteri.icimler.all()[:12]
    durum["kahveler"] = Kahve.objects.filter(aktif=True)[:6]
    return render(request, "kahve/kart.html", durum)


# --------------------------------------------------------------------------
# Web - kasa (personel)
# Sepet oturumda tutulur; satis tamamlanana kadar veritabanina yazilmaz.
# --------------------------------------------------------------------------

@staff_member_required
def kasa(request):
    return render(
        request,
        "kahve/kasa.html",
        {
            "ayar": KahveAyar.al(),
            "gruplar": _kategorilere_gore(
                Kahve.objects.filter(aktif=True).select_related("kategori")
            ),
            "gun": kasa_sepeti.gunun_ozeti(),
        },
    )


def _kasa_cevabi(request, mesaj="", ek=None):
    govde = {"ok": True, "mesaj": mesaj, "sepet": kasa_sepeti.ozet(request)}
    if ek:
        govde.update(ek)
    return JsonResponse(govde)


@staff_member_required
def kasa_durum(request):
    return _kasa_cevabi(request)


@staff_member_required
def kasa_borc_musterileri(request):
    """Kirtasiye tarafindaki musteri listesi - kahve kasasinda borca yazmak icin.

    Ayni musteri kaydi iki tezgahta da kullanilir; kahve borcu da ayni
    borc hanesine islenir.
    """
    aranan = (request.GET.get("q") or "").strip()
    sorgu = Musteri.objects.all()
    if aranan:
        sorgu = sorgu.filter(
            Q(isim_soyisim__icontains=aranan) | Q(Cep_Telefonu__icontains=aranan)
        )
    sorgu = sorgu.order_by("isim_soyisim")[:40]
    return JsonResponse({
        "ok": True,
        "musteriler": [
            {
                "id": m.id,
                "ad": m.isim_soyisim,
                "telefon": str(m.Cep_Telefonu) if m.Cep_Telefonu else "",
                "borc": float(m.borc),
            }
            for m in sorgu
        ],
    })


@staff_member_required
@require_POST
def kasa_indirim(request):
    """Kahve sepetine ozel indirim uygular ya da kaldirir."""
    veri = _govde(request)
    try:
        indirim_modulu.yaz(
            request, veri.get("tur", "tl"), veri.get("deger", "0"),
            indirim_modulu.KAHVE_ANAHTAR,
        )
    except indirim_modulu.IndirimHatasi as hata:
        return JsonResponse({"ok": False, "hata": str(hata)}, status=400)
    return _kasa_cevabi(request, "İndirim güncellendi.")


@staff_member_required
@require_POST
def kasa_sepete_ekle(request):
    veri = _govde(request)
    kahve = Kahve.objects.filter(pk=veri.get("kahve_id"), aktif=True).first()
    if kahve is None:
        return JsonResponse({"ok": False, "hata": "Kahve bulunamadi."}, status=404)
    kasa_sepeti.sepete_ekle(request, kahve.id)
    return _kasa_cevabi(request, f"{kahve.ad} eklendi.")


@staff_member_required
@require_POST
def kasa_adet_degistir(request):
    veri = _govde(request)
    try:
        adet = int(veri.get("adet", 1))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "hata": "Adet sayi olmali."}, status=400)
    kasa_sepeti.adet_degistir(request, int(veri.get("kahve_id", 0)), adet)
    return _kasa_cevabi(request)


@staff_member_required
@require_POST
def kasa_satir_sil(request):
    kasa_sepeti.satir_sil(request, int(_govde(request).get("kahve_id", 0)))
    return _kasa_cevabi(request)


@staff_member_required
@require_POST
def kasa_hediye_degistir(request):
    veri = _govde(request)
    try:
        hediye_adet = int(veri.get("hediye_adet", 0))
    except (TypeError, ValueError):
        return JsonResponse({"ok": False, "hata": "Hediye adedi sayi olmali."}, status=400)
    kasa_sepeti.hediye_degistir(request, int(veri.get("kahve_id", 0)), hediye_adet)
    return _kasa_cevabi(request)


@staff_member_required
@require_POST
def kasa_sepeti_temizle(request):
    kasa_sepeti.sepeti_temizle(request)
    kasa_sepeti.indirimi_temizle(request)   # kasa sifirlaninca indirim de gitsin
    return _kasa_cevabi(request, "Kasa sifirlandi.")


def _kod_ile_musteri(kod):
    """Barkod, QR jetonu ya da QR adresi ile musteriyi bulur."""
    kod = (kod or "").strip()
    if not kod:
        return None
    musteri = KahveMusteri.objects.filter(kod=kod, aktif=True).first()
    if musteri is None:
        jeton = kod.rstrip("/").split("/")[-1]
        if len(jeton) >= 32:
            musteri = KahveMusteri.objects.filter(qr_token=jeton, aktif=True).first()
    return musteri


@staff_member_required
@require_POST
def kasa_musteri_bul(request):
    kod = (_govde(request).get("kod") or "").strip()
    if not kod:
        return JsonResponse({"ok": False, "hata": "Barkod veya QR okutun."}, status=400)

    musteri = _kod_ile_musteri(kod)
    if musteri is None:
        return JsonResponse({"ok": False, "hata": "Bu koda ait musteri yok."}, status=404)

    kasa_sepeti.musteri_bagla(request, musteri)
    return _kasa_cevabi(request, f"{musteri.ad_soyad} karti okundu.")


@staff_member_required
@require_POST
def kasa_musteri_cikar(request):
    kasa_sepeti.musteri_bagla(request, None)
    return _kasa_cevabi(request, "Musteri karti cikarildi.")


@staff_member_required
@require_POST
def kasa_musteri_ekle(request):
    veri = _govde(request)
    ad_soyad = (veri.get("ad_soyad") or "").strip()
    if not ad_soyad:
        return JsonResponse({"ok": False, "hata": "Ad soyad gerekli."}, status=400)
    musteri = KahveMusteri.objects.create(
        ad_soyad=ad_soyad,
        telefon=(veri.get("telefon") or "").strip(),
        email=(veri.get("email") or "").strip(),
    )
    kasa_sepeti.musteri_bagla(request, musteri)
    return _kasa_cevabi(request, f"{musteri.ad_soyad} acildi. Barkod: {musteri.kod}")


@staff_member_required
@require_POST
def kasa_satis_tamamla(request):
    veri = _govde(request)
    try:
        sonuc = kasa_sepeti.satisi_tamamla(
            request,
            odeme_turu=veri.get("odeme_turu"),
            nakit=veri.get("nakit"),
            kart=veri.get("kart"),
            kasiyer=request.user.get_username(),
            borc_musteri_id=veri.get("borc_musteri_id"),
            not_metni=(veri.get("not") or "").strip(),
        )
    except kasa_sepeti.SatisHatasi as hata:
        return JsonResponse({"ok": False, "hata": str(hata)}, status=400)

    satis = sonuc["satis"]
    return _kasa_cevabi(
        request,
        "Satis tamamlandi.",
        {
            "satis": {
                "id": satis.id,
                "toplam": float(satis.toplam),
                "nakit": float(satis.nakit_tutar),
                "kart": float(satis.kart_tutar),
                "odeme": satis.get_odeme_turu_display(),
                "fincan": satis.fincan_adedi,
                "hediye": satis.hediye_adedi,
                "indirim": float(satis.indirim_tutari),
                "borc_musteri": satis.borc_musteri.isim_soyisim if satis.borc_musteri else None,
                "yeni_borc": float(satis.borc_musteri.borc) if satis.borc_musteri else None,
            },
            "kazanilan_hediye": sonuc["kazanilan_hediye"],
            "gun": kasa_sepeti.gunun_ozeti(),
        },
    )


# --------------------------------------------------------------------------
# Cron - gunluk sure temizligi
# --------------------------------------------------------------------------

@csrf_exempt
def cron_temizlik(request):
    """Her gece calisir. Suresi dolan kahveleri sayactan duser.

    Ornek: .../kahve/cron/gunluk-temizlik/?anahtar=XXXX
    """
    ayar = KahveAyar.al()
    anahtar = request.GET.get("anahtar") or request.META.get("HTTP_X_KAHVE_KEY", "")
    if not _esit_mi(anahtar, ayar.cron_anahtari):
        return JsonResponse({"ok": False, "hata": "Gecersiz anahtar."}, status=403)

    dusen = sadakat.suresi_dolanlari_dusur()
    return JsonResponse(
        {
            "ok": True,
            "dusen_kahve": dusen,
            "gecerlilik_gun": ayar.gecerlilik_gun,
            "hediye_icin_kahve": ayar.hediye_icin_kahve,
            "calisma_zamani": timezone.localtime().isoformat(),
        }
    )


# --------------------------------------------------------------------------
# Mobil API (v1) - hepsi X-Kahve-Key basligi ister
# --------------------------------------------------------------------------

@csrf_exempt
@mobil_anahtar_gerekli
def api_ayarlar(request):
    ayar = KahveAyar.al()
    return JsonResponse(
        {
            "ok": True,
            "isletme_adi": ayar.isletme_adi,
            "slogan": ayar.slogan,
            "hediye_icin_kahve": ayar.hediye_icin_kahve,
            "gecerlilik_gun": ayar.gecerlilik_gun,
            "firebase": ayar.firebase_web_config() if ayar.firebase_hazir else None,
        }
    )


@csrf_exempt
@mobil_anahtar_gerekli
def api_menu(request):
    kahveler = Kahve.objects.filter(aktif=True).select_related("kategori")
    return JsonResponse({"ok": True, "kahveler": [_kahve_ozet(k, request) for k in kahveler]})


@csrf_exempt
@require_POST
@mobil_anahtar_gerekli
def api_oturum(request):
    """Mobil uygulama Firebase ile giris yapip token'i buraya gonderir."""
    ayar = KahveAyar.al()
    veri = _govde(request)
    try:
        bilgi = token_dogrula(veri.get("id_token"), ayar.firebase_api_key)
    except FirebaseHatasi as hata:
        return JsonResponse({"ok": False, "hata": str(hata)}, status=401)

    musteri, yeni = KahveMusteri.objects.get_or_create(
        firebase_uid=bilgi["uid"],
        defaults={
            "ad_soyad": bilgi["ad_soyad"] or bilgi["email"].split("@")[0] or "Kahve dostu",
            "email": bilgi["email"],
            "telefon": bilgi["telefon"],
        },
    )
    return JsonResponse({"ok": True, "yeni_kayit": yeni, "musteri": _musteri_ozet(musteri)})


@csrf_exempt
@mobil_anahtar_gerekli
def api_kart(request):
    musteri, hata = _bearer_musterisi(request)
    if musteri is None:
        return JsonResponse({"ok": False, "hata": hata}, status=401)
    return JsonResponse(
        {
            "ok": True,
            "musteri": _musteri_ozet(musteri),
            "qr_adresi": request.build_absolute_uri(f"/kahve/k/{musteri.qr_token}/"),
        }
    )


@csrf_exempt
@mobil_anahtar_gerekli
def api_gecmis(request):
    musteri, hata = _bearer_musterisi(request)
    if musteri is None:
        return JsonResponse({"ok": False, "hata": hata}, status=401)
    kayitlar = musteri.icimler.all()[:50]
    return JsonResponse(
        {
            "ok": True,
            "kayitlar": [
                {
                    "id": k.id,
                    "kahve": k.kahve_adi,
                    "fiyat": float(k.fiyat),
                    "durum": k.durum,
                    "durum_adi": k.get_durum_display(),
                    "tarih": k.tarih.isoformat(),
                    "son_gecerlilik": k.son_gecerlilik.isoformat() if k.son_gecerlilik else None,
                    "kalan_gun": k.kalan_gun,
                }
                for k in kayitlar
            ],
            "hediyeler": [
                {
                    "id": h.id,
                    "durum": h.durum,
                    "kazanma_tarihi": h.kazanma_tarihi.isoformat(),
                    "kullanma_tarihi": h.kullanma_tarihi.isoformat() if h.kullanma_tarihi else None,
                }
                for h in musteri.hediyeler.all()[:20]
            ],
        }
    )
