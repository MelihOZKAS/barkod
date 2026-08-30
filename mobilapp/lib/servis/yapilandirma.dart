/// Sunucu ayarlari derleme aninda verilir, koda gomulmez:
///   flutter run --dart-define=KAHVE_SUNUCU=https://site.com \
///               --dart-define=KAHVE_ANAHTAR=... (admin panelindeki Mobil API anahtari)
class Yapilandirma {
  const Yapilandirma._();

  static const sunucu = String.fromEnvironment('KAHVE_SUNUCU');
  static const apiAnahtari = String.fromEnvironment('KAHVE_ANAHTAR');

  /// Sunucu tanimli degilse uygulama demo veriyle calisir.
  static bool get bagli => sunucu.isNotEmpty && apiAnahtari.isNotEmpty;
}
