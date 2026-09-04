"""Barkod cizimi -- disaridan paket gerektirmez.

Raf etiketine basilacak barkod burada SVG olarak uretilir. python-barcode gibi
bir paket kurmak yerine kodlama elle yazildi; proje kurali yeni bagimlilik
eklememek.

Hangi simgeleme secilir:

  * 13 haneli ve kontrol hanesi tutuyorsa -> EAN-13
  *  8 haneli ve kontrol hanesi tutuyorsa -> EAN-8
  * geri kalan her sey                    -> Code 128

Kontrol hanesi tutmayan bir sayiyi EAN olarak cizmiyoruz: okuyucu oyle bir
barkodu hic okumaz, etiket sessizce ise yaramaz olur. Code 128 sayinin kendisini
oldugu gibi tasir; okutuldugunda ekranda yazan rakamlarin ayni cikar.

Uretilen SVG dogrudan sabloma basilir, diske resim yazilmaz.
"""

from django.utils.safestring import mark_safe

# EAN kod tablolari. SAG = SOL_TEK'in birebir tersi (0<->1),
# SOL_CIFT = SAG'in ters cevrilmis hali. barkod testleri bu bagintiyi
# dogruluyor; tabloya elle dokunulursa yazim hatasi oradan yakalanir.
SOL_TEK = (
    "0001101", "0011001", "0010011", "0111101", "0100011",
    "0110001", "0101111", "0111011", "0110111", "0001011",
)
SOL_CIFT = (
    "0100111", "0110011", "0011011", "0100001", "0011101",
    "0111001", "0000101", "0010001", "0001001", "0010111",
)
SAG = (
    "1110010", "1100110", "1101100", "1000010", "1011100",
    "1001110", "1010000", "1000100", "1001000", "1110100",
)

# EAN-13'te ilk hane cizilmez; soldaki alti hanenin tek/cift dizilisiyle anlatilir.
ILK_HANE_DESENI = (
    "TTTTTT", "TTCTCC", "TTCCTC", "TTCCCT", "TCTTCC",
    "TCCTTC", "TCCCTT", "TCTCTC", "TCTCCT", "TCCTCT",
)

KENAR = "101"     # bas ve son koruma cubuklari
ORTA = "01010"    # ortadaki koruma cubugu

# Code 128: 107 desen. Her desen cubuk/bosluk genisliklerini sirayla verir,
# cubukla baslar. 103/104/105 baslangic, 106 bitis deseni.
CODE128_DESENLERI = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
)
CODE128_BASLA_B = 104
CODE128_BASLA_C = 105
CODE128_BITIR = 106
CODE128_B_DEN_C_YE = 99
CODE128_C_DEN_B_YE = 100

# Sessiz alan (quiet zone): barkodun iki yanindaki bos modul sayisi. Eksik
# birakilirsa okuyucu barkodun nerede bittigini anlayamaz.
EAN_SESSIZ_SOL = 11
EAN_SESSIZ_SAG = 7
CODE128_SESSIZ = 10


class Barkod:
    """Cizilmis bir barkod: SVG'si, altina yazilacak metni ve simgelemesi."""

    def __init__(self, metin, tur, moduller):
        self.metin = metin
        self.tur = tur
        self.moduller = moduller  # "0"/"1" dizisi; sessiz alanlar dahil

    @property
    def genislik(self):
        return len(self.moduller)

    @property
    def svg(self):
        return mark_safe(self._svg())

    def _svg(self):
        """Bitisik ayni renkteki modulleri tek dikdortgende birlestirir.

        95 modul icin 95 <rect> yazmak sayfayi sisirir; birlestirince ortalama
        30 civari dikdortgen kaliyor.
        """
        parcalar = [
            f'<svg class="barkod-svg" viewBox="0 0 {self.genislik} 100" '
            f'preserveAspectRatio="none" role="img" '
            f'aria-label="Barkod {self.metin}">',
            f'<rect width="{self.genislik}" height="100" fill="#fff"/>',
        ]
        basla = 0
        while basla < self.genislik:
            son = basla
            while son < self.genislik and self.moduller[son] == self.moduller[basla]:
                son += 1
            if self.moduller[basla] == "1":
                parcalar.append(
                    f'<rect x="{basla}" y="0" width="{son - basla}" height="100" fill="#000"/>'
                )
            basla = son
        parcalar.append("</svg>")
        return "".join(parcalar)


def ean_kontrol_hanesi(rakamlar):
    """EAN-8/EAN-13 kontrol hanesi. rakamlar: son hane HARIC tum haneler."""
    toplam = 0
    # Sagdan sola 1,3,1,3... agirlik. Son haneden geriye sayarak yaziliyor ki
    # 7 haneli (EAN-8) ve 12 haneli (EAN-13) girdide ayni formul calissin.
    for sira, hane in enumerate(reversed(rakamlar)):
        toplam += int(hane) * (3 if sira % 2 == 0 else 1)
    return (10 - toplam % 10) % 10


def _ean_gecerli(rakamlar):
    return int(rakamlar[-1]) == ean_kontrol_hanesi(rakamlar[:-1])


def ean13_moduller(rakamlar):
    desen = ILK_HANE_DESENI[int(rakamlar[0])]
    sol = "".join(
        (SOL_TEK if desen[i] == "T" else SOL_CIFT)[int(hane)]
        for i, hane in enumerate(rakamlar[1:7])
    )
    sag = "".join(SAG[int(hane)] for hane in rakamlar[7:])
    return KENAR + sol + ORTA + sag + KENAR


def ean8_moduller(rakamlar):
    sol = "".join(SOL_TEK[int(hane)] for hane in rakamlar[:4])
    sag = "".join(SAG[int(hane)] for hane in rakamlar[4:])
    return KENAR + sol + ORTA + sag + KENAR


def code128_degerleri(metin):
    """Metni Code 128 sembol degerlerine cevirir (baslangic ve kontrol dahil).

    Rakam ciftleri C kumesinde iki hane birden kodlanir, yani barkod yariya
    iner. Tek sayida hane kalirsa o hane B kumesinde yazilir.
    """
    degerler = []
    konum = 0
    uzunluk = len(metin)

    def kalan_rakam(bastan):
        sayac = 0
        while bastan + sayac < uzunluk and metin[bastan + sayac].isdigit():
            sayac += 1
        return sayac

    # Bastaki rakam sayisi cift ve en az 4 ise C kumesiyle baslamak karli.
    rakam = kalan_rakam(0)
    c_kumesinde = rakam >= 4 and rakam % 2 == 0
    degerler.append(CODE128_BASLA_C if c_kumesinde else CODE128_BASLA_B)

    while konum < uzunluk:
        if c_kumesinde:
            if konum + 1 < uzunluk and metin[konum].isdigit() and metin[konum + 1].isdigit():
                degerler.append(int(metin[konum:konum + 2]))
                konum += 2
            else:
                degerler.append(CODE128_C_DEN_B_YE)
                c_kumesinde = False
        else:
            rakam = kalan_rakam(konum)
            if rakam >= 6 and rakam % 2 == 0:
                degerler.append(CODE128_B_DEN_C_YE)
                c_kumesinde = True
                continue
            degerler.append(ord(metin[konum]) - 32)
            konum += 1

    kontrol = degerler[0]
    for sira, deger in enumerate(degerler[1:], start=1):
        kontrol += sira * deger
    degerler.append(kontrol % 103)
    degerler.append(CODE128_BITIR)
    return degerler


def code128_moduller(metin):
    moduller = []
    for deger in code128_degerleri(metin):
        cubuk = True
        for genislik in CODE128_DESENLERI[deger]:
            moduller.append(("1" if cubuk else "0") * int(genislik))
            cubuk = not cubuk
    return "".join(moduller)


def barkod_ciz(deger):
    """Bir barkod degerinden Barkod nesnesi uretir; bos deger icin None doner."""
    metin = str(deger or "").strip()
    if not metin:
        return None

    if metin.isdigit() and len(metin) == 13 and _ean_gecerli(metin):
        govde = ean13_moduller(metin)
        return Barkod(metin, "EAN-13",
                      "0" * EAN_SESSIZ_SOL + govde + "0" * EAN_SESSIZ_SAG)

    if metin.isdigit() and len(metin) == 8 and _ean_gecerli(metin):
        govde = ean8_moduller(metin)
        return Barkod(metin, "EAN-8",
                      "0" * EAN_SESSIZ_SOL + govde + "0" * EAN_SESSIZ_SAG)

    # Code 128 sadece basilabilir ASCII tasir. Barkod alani sayi oldugu icin
    # normalde buraya hep rakam gelir; yine de guvence olsun.
    if any(not (32 <= ord(karakter) <= 126) for karakter in metin):
        return None
    govde = code128_moduller(metin)
    return Barkod(metin, "Code 128",
                  "0" * CODE128_SESSIZ + govde + "0" * CODE128_SESSIZ)
