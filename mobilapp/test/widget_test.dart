import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobilapp/ekranlar/ana_ekran.dart';
import 'package:mobilapp/ekranlar/giris_ekrani.dart';
import 'package:mobilapp/demo_veri.dart';
import 'package:mobilapp/ekranlar/menu_sekmesi.dart';
import 'package:mobilapp/ekranlar/profil_sekmesi.dart';
import 'package:mobilapp/main.dart';
import 'package:mobilapp/modeller/kart.dart';

void main() {
  testWidgets('Giris ekrani acilir ve butona basinca ana ekrana gecer', (tester) async {
    await tester.pumpWidget(const KahveUygulamasi());

    expect(find.byType(GirisEkrani), findsOneWidget);
    expect(find.text('Giriş yap'), findsOneWidget);

    await tester.tap(find.text('Giriş yap'));
    await tester.pump();                                   // yukleniyor durumu
    await tester.pump(const Duration(milliseconds: 600));  // gecis
    await tester.pumpAndSettle();

    expect(find.byType(AnaEkran), findsOneWidget);
  });

  testWidgets('Alt navigasyon Menu ve Kartim sekmelerini gosterir', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: AnaEkran()));
    await tester.pumpAndSettle();

    expect(find.text('Menü'), findsOneWidget);
    expect(find.text('Kartım'), findsOneWidget);
    expect(find.text('Bugün ne içiyoruz?'), findsOneWidget);

    await tester.tap(find.text('Kartım'));
    await tester.pumpAndSettle();

    expect(find.text('Kasada okut'), findsOneWidget);
    expect(find.text('SADAKAT KARTI'), findsOneWidget);

    // sayac kutulari listenin altinda, once oraya kaydir
    await tester.drag(find.byType(ListView), const Offset(0, -700));
    await tester.pumpAndSettle();

    expect(find.text('Toplam içtiğin'), findsOneWidget);
    expect(find.text('Hediyeye kalan'), findsOneWidget);
    expect(find.text('Bekleyen hediye'), findsOneWidget);
  });

  testWidgets('Kasada okut tam ekran QR sayfasini acar', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: AnaEkran()));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Kartım'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Kasada okut'));
    await tester.pumpAndSettle();

    expect(find.text('KASADA OKUT'), findsOneWidget);
    expect(find.text('Okunmazsa ekran parlaklığını artırın'), findsOneWidget);

    await tester.tap(find.byTooltip('Kapat'));
    await tester.pumpAndSettle();
    expect(find.text('KASADA OKUT'), findsNothing);
  });

  testWidgets('Bekleyen hediye varken menu ve kart tasmadan cizilir', (tester) async {
    final k = DemoVeri.kart;
    final hediyeliKart = Kart(
      adSoyad: k.adSoyad,
      kod: k.kod,
      aktifKahve: 0,
      esik: k.esik,
      kalan: k.esik,
      bekleyenHediye: 1,
      toplamIcim: k.toplamIcim,
      damgalar: const [
        Damga(sira: 1, dolu: false),
        Damga(sira: 2, dolu: false),
        Damga(sira: 3, dolu: false),
        Damga(sira: 4, dolu: false),
        Damga(sira: 5, dolu: false),
      ],
    );

    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: MenuSekmesi(kart: hediyeliKart, karta: () {}))),
    );
    await tester.pumpAndSettle();

    expect(find.text('Bir kahve hediye'), findsOneWidget);
    expect(find.text('HEDİYENLE ALABİLİRSİN'), findsWidgets);

    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: ProfilSekmesi(kart: hediyeliKart))),
    );
    await tester.pumpAndSettle();

    expect(find.text('Sıradaki kahven bizden.'), findsOneWidget);
    expect(find.text('1 HEDİYE'), findsOneWidget);
  });
}
