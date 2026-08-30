import '../demo_veri.dart';
import 'api.dart';
import 'yapilandirma.dart';

/// Sunucudaki isletme ayarlari (/api/v1/ayarlar/).
///
/// Bir kez cekilir, uygulama boyunca onbellekte durur. Sunucuya ulasilamazsa
/// demo degerlere duser — uygulama asla bos ekran gostermez.
class Ayarlar {
  const Ayarlar({
    required this.isletmeAdi,
    required this.hediyeIcinKahve,
    required this.gecerlilikGun,
    required this.sunucudan,
  });

  final String isletmeAdi;
  final int hediyeIcinKahve;
  final int gecerlilikGun;

  /// false ise demo degerler kullaniliyor demektir.
  final bool sunucudan;

  static const varsayilan = Ayarlar(
    isletmeAdi: DemoVeri.isletmeAdi,
    hediyeIcinKahve: 5,
    gecerlilikGun: DemoVeri.gecerlilikGun,
    sunucudan: false,
  );

  static Ayarlar _onbellek = varsayilan;
  static Future<Ayarlar>? _istek;

  static Ayarlar get simdiki => _onbellek;

  /// Ayarlari getirir. Ayni anda birden fazla cagri gelse de tek istek atilir.
  static Future<Ayarlar> getir() {
    if (!Yapilandirma.bagli) return Future.value(varsayilan);
    return _istek ??= _cek();
  }

  static Future<Ayarlar> _cek() async {
    try {
      final govde = await KahveApi().ayarlar();
      _onbellek = Ayarlar(
        isletmeAdi: (govde['isletme_adi'] as String?)?.trim().isNotEmpty == true
            ? govde['isletme_adi'] as String
            : DemoVeri.isletmeAdi,
        hediyeIcinKahve: (govde['hediye_icin_kahve'] as num?)?.toInt() ?? 5,
        gecerlilikGun: (govde['gecerlilik_gun'] as num?)?.toInt() ?? DemoVeri.gecerlilikGun,
        sunucudan: true,
      );
    } on Object {
      _onbellek = varsayilan; // sunucuya ulasilamadi
    } finally {
      _istek = null;
    }
    return _onbellek;
  }
}
