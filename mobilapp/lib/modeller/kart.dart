// Sunucudaki /kahve/api/v1/ cevaplarinin Dart karsiligi.

class Damga {
  const Damga({required this.sira, required this.dolu, this.kalanGun, this.kahveAdi});

  final int sira;
  final bool dolu;
  final int? kalanGun;
  final String? kahveAdi;

  bool get sonuyor => dolu && kalanGun != null && kalanGun! <= 3;

  factory Damga.jsondan(Map<String, dynamic> j) => Damga(
        sira: j['sira'] as int,
        dolu: j['dolu'] as bool,
        kalanGun: j['kalan_gun'] as int?,
        kahveAdi: j['kahve_adi'] as String?,
      );
}

class Kart {
  const Kart({
    required this.adSoyad,
    required this.kod,
    required this.aktifKahve,
    required this.esik,
    required this.kalan,
    required this.bekleyenHediye,
    required this.toplamIcim,
    required this.damgalar,
  });

  final String adSoyad;
  final String kod;
  final int aktifKahve;
  final int esik;
  final int kalan;
  final int bekleyenHediye;
  final int toplamIcim;
  final List<Damga> damgalar;

  factory Kart.jsondan(Map<String, dynamic> j) => Kart(
        adSoyad: j['ad_soyad'] as String? ?? '',
        kod: j['kod'] as String? ?? '',
        aktifKahve: j['aktif_kahve'] as int? ?? 0,
        esik: j['esik'] as int? ?? 5,
        kalan: j['kalan'] as int? ?? 0,
        bekleyenHediye: j['bekleyen_hediye'] as int? ?? 0,
        toplamIcim: j['toplam_icim'] as int? ?? 0,
        damgalar: ((j['damgalar'] as List?) ?? [])
            .map((d) => Damga.jsondan(d as Map<String, dynamic>))
            .toList(),
      );
}

/// Sunucu http:// donerse https'e cevirir.
///
/// Android release derlemesi duz HTTP'yi engelliyor; TLS'i Cloudflare
/// sonlandirdigi icin Django bir donem "http://" adresler uretiyordu ve
/// urun fotograflarinin hicbiri yuklenmiyordu. Sunucu tarafi duzeltildi,
/// bu da ikinci emniyet: ayni hata tekrarlarsa uygulama etkilenmesin.
String _guvenliAdres(String adres) =>
    adres.startsWith('http://') ? adres.replaceFirst('http://', 'https://') : adres;

class KahveUrun {
  const KahveUrun({
    required this.ad,
    required this.fiyat,
    this.aciklama = '',
    this.icindekiler = const [],
    this.gorsel = '',
    this.hediyeGecerli = true,
    this.kategori = '',
  });

  final String ad;
  final double fiyat;
  final String aciklama;
  final List<String> icindekiler;
  final String gorsel;

  /// Hediye kahve olarak verilebilir mi (admin panelinden kapatilabilir).
  final bool hediyeGecerli;

  /// Menu bolumu: Sicak Icecekler, Soguk Icecekler... Bos ise "Diger".
  final String kategori;

  factory KahveUrun.jsondan(Map<String, dynamic> j) => KahveUrun(
        ad: j['ad'] as String? ?? '',
        fiyat: (j['fiyat'] as num?)?.toDouble() ?? 0,
        aciklama: j['aciklama'] as String? ?? '',
        icindekiler: ((j['icindekiler'] as List?) ?? []).map((e) => e.toString()).toList(),
        gorsel: _guvenliAdres(j['gorsel'] as String? ?? ''),
        hediyeGecerli: j['hediye_gecerli'] as bool? ?? true,
        kategori: j['kategori'] as String? ?? '',
      );
}
