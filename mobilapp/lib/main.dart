import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'demo_veri.dart';
import 'ekranlar/giris_ekrani.dart';
import 'tema.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: KahveRenk.espresso2,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );
  runApp(const KahveUygulamasi());
}

class KahveUygulamasi extends StatelessWidget {
  const KahveUygulamasi({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: DemoVeri.isletmeAdi,
      debugShowCheckedModeBanner: false,
      theme: kahveTemasi(),
      home: const GirisEkrani(),
    );
  }
}
