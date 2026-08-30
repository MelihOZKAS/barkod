import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Kahve modulunun tasarim belirteci.
/// Palet: kavrulmus cekirdek koyulugu + bal/krema amberi + Iznik cini mavisi.
/// Web tarafiyla (kahve/static/kahve/kahve.css) ayni degerler.
class KahveRenk {
  const KahveRenk._();

  static const espresso = Color(0xFF1C1411);
  static const espresso2 = Color(0xFF261B16);
  static const espresso3 = Color(0xFF33251E);
  static const crema = Color(0xFFD69A4C);
  static const cremaAcik = Color(0xFFF1C68C);
  static const cini = Color(0xFF2E6B78);
  static const ciniAcik = Color(0xFF59A0AC);
  static const porselen = Color(0xFFF2F1EE);
  static const kabuk = Color(0xFFA29386);
  static const uyari = Color(0xFFC9563B);
}

/// 8pt grid.
class Aralik {
  const Aralik._();

  static const b1 = 8.0;
  static const b2 = 16.0;
  static const b3 = 24.0;
  static const b4 = 32.0;
  static const b5 = 48.0;
  static const b6 = 64.0;
}

class Yuvarlaklik {
  const Yuvarlaklik._();

  static const s = 12.0;
  static const m = 16.0;
  static const l = 24.0;
}

/// Baslik / veri fontlari. Govde fontu tema uzerinden gelir.
TextStyle baslikStili({
  double boyut = 32,
  FontWeight agirlik = FontWeight.w700,
  Color renk = KahveRenk.porselen,
  double aralik = -0.8,
  double? satirYuksekligi,
}) =>
    GoogleFonts.bricolageGrotesque(
      fontSize: boyut,
      fontWeight: agirlik,
      color: renk,
      letterSpacing: aralik,
      height: satirYuksekligi,
    );

TextStyle veriStili({
  double boyut = 13,
  FontWeight agirlik = FontWeight.w500,
  Color renk = KahveRenk.crema,
  double aralik = 0.6,
}) =>
    GoogleFonts.jetBrainsMono(
      fontSize: boyut,
      fontWeight: agirlik,
      color: renk,
      letterSpacing: aralik,
    );

/// Kucuk, harfleri aralikli ust etiket.
TextStyle etiketStili({Color renk = KahveRenk.crema}) => GoogleFonts.jetBrainsMono(
      fontSize: 11,
      fontWeight: FontWeight.w500,
      color: renk,
      letterSpacing: 1.8,
    );

ThemeData kahveTemasi() {
  final govde = GoogleFonts.instrumentSansTextTheme(ThemeData.dark().textTheme);

  return ThemeData(
    useMaterial3: true,
    scaffoldBackgroundColor: KahveRenk.espresso,
    colorScheme: const ColorScheme.dark(
      primary: KahveRenk.crema,
      onPrimary: Color(0xFF2A1B0C),
      secondary: KahveRenk.cini,
      onSecondary: KahveRenk.porselen,
      surface: KahveRenk.espresso2,
      onSurface: KahveRenk.porselen,
      error: KahveRenk.uyari,
    ),
    textTheme: govde.apply(
      bodyColor: KahveRenk.porselen,
      displayColor: KahveRenk.porselen,
    ),
    splashFactory: InkSparkle.splashFactory,
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: KahveRenk.crema,
        foregroundColor: const Color(0xFF2A1B0C),
        minimumSize: const Size.fromHeight(56),
        shape: const StadiumBorder(),
        textStyle: GoogleFonts.instrumentSans(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: KahveRenk.porselen,
        minimumSize: const Size.fromHeight(56),
        side: BorderSide(color: KahveRenk.porselen.withValues(alpha: .22)),
        shape: const StadiumBorder(),
        textStyle: GoogleFonts.instrumentSans(fontSize: 16, fontWeight: FontWeight.w600),
      ),
    ),
  );
}
