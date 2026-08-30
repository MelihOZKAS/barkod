import 'modeller/kart.dart';

/// Sunucu tanimli degilken (Yapilandirma.bagli == false) kullanilan ornek veri.
/// Gercek veri /kahve/api/v1/ uzerinden gelir.
class DemoVeri {
  const DemoVeri._();

  static const isletmeAdi = 'Atlas Coffee';
  static const gecerlilikGun = 30;

  /// Sunucudan gelen esige gore ornek kart uretir (kart verisi Firebase'e kadar demo).
  static Kart kartUret(int esik) {
    final dolu = esik <= 3 ? 1 : 3;
    return Kart(
      adSoyad: kart.adSoyad,
      kod: kart.kod,
      aktifKahve: dolu,
      esik: esik,
      kalan: esik - dolu,
      bekleyenHediye: 0,
      toplamIcim: kart.toplamIcim,
      damgalar: [
        for (var i = 0; i < esik; i++)
          Damga(
            sira: i + 1,
            dolu: i < dolu,
            kalanGun: i < dolu ? (i == 0 ? 2 : 18 + i) : null,
          ),
      ],
    );
  }

  static final kart = Kart(
    adSoyad: 'Melih Ozkas',
    kod: '899638940232',
    aktifKahve: 3,
    esik: 5,
    kalan: 2,
    bekleyenHediye: 0,
    toplamIcim: 12,
    damgalar: const [
      Damga(sira: 1, dolu: true, kalanGun: 2, kahveAdi: 'Turk Kahvesi'),
      Damga(sira: 2, dolu: true, kalanGun: 18, kahveAdi: 'Latte'),
      Damga(sira: 3, dolu: true, kalanGun: 28, kahveAdi: 'Flat White'),
      Damga(sira: 4, dolu: false),
      Damga(sira: 5, dolu: false),
    ],
  );

  static const menu = <KahveUrun>[
    KahveUrun(
      ad: 'Türk Kahvesi',
      kategori: 'Sıcak İçecekler',
      fiyat: 60,
      aciklama: 'Köpüğü bol, bakır cezvede pişirilir.',
      icindekiler: ['Kavrulmuş çekirdek', 'Su'],
      gorsel: 'assets/gorseller/turk-kahvesi.jpg',
    ),
    KahveUrun(
      ad: 'Espresso',
      kategori: 'Sıcak İçecekler',
      fiyat: 70,
      aciklama: 'Tek shot, 25 saniye, 30 ml.',
      icindekiler: ['Espresso'],
      gorsel: 'assets/gorseller/espresso.jpg',
    ),
    KahveUrun(
      ad: 'Latte',
      kategori: 'Sıcak İçecekler',
      fiyat: 90,
      aciklama: 'İpeksi süt köpüğü, yumuşak içim.',
      icindekiler: ['Espresso', 'Süt', 'Süt köpüğü'],
      gorsel: 'assets/gorseller/latte.jpg',
    ),
    KahveUrun(
      ad: 'Flat White',
      kategori: 'Sıcak İçecekler',
      fiyat: 95,
      aciklama: 'Daha yoğun kahve, ince köpük.',
      icindekiler: ['Çift espresso', 'Süt'],
      gorsel: 'assets/gorseller/flat-white.jpg',
    ),
    KahveUrun(
      ad: 'Filtre Kahve',
      kategori: 'Sıcak İçecekler',
      fiyat: 75,
      aciklama: 'Günün demlemesi, V60.',
      icindekiler: ['Öğütülmüş kahve', 'Su'],
      gorsel: 'assets/gorseller/filtre-kahve.jpg',
    ),
    KahveUrun(
      ad: 'Cortado',
      kategori: 'Soğuk İçecekler',
      fiyat: 85,
      aciklama: 'Yarı kahve yarı süt.',
      icindekiler: ['Espresso', 'Sıcak süt'],
      gorsel: 'assets/gorseller/cortado.jpg',
    ),
  ];
}
