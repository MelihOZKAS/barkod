import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mobilapp/ekranlar/ana_ekran.dart';
import 'package:mobilapp/ekranlar/giris_ekrani.dart';
import 'package:mobilapp/demo_veri.dart';
import 'package:mobilapp/ekranlar/menu_sekmesi.dart';
import 'package:mobilapp/ekranlar/profil_sekmesi.dart';
import 'package:mobilapp/main.dart';
import 'package:mobilapp/modeller/kart.dart';
import 'package:mobilapp/parcalar/damga_halkasi.dart';

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

  testWidgets('Alt bar iki sekme, kategoriler menunun ustunde', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: AnaEkran()));
    await tester.pumpAndSettle();

    // Alt bar sadece iki sekme
    expect(find.text('Menü'), findsOneWidget);
    expect(find.text('Kartım'), findsOneWidget);

    // Kategori seridi urun ekraninin ustunde
    expect(find.text('Tümü'), findsOneWidget);
    expect(find.text('Bugün ne içiyoruz?'), findsOneWidget);

    // Kategori secince baslik degisir, sekme Menu'de kalir
    final kategori = DemoVeri.menu.first.kategori;
    await tester.tap(find.text(kategori));
    await tester.pumpAndSettle();
    expect(find.text(kategori), findsWidgets);
    expect(find.text('Bugün ne içiyoruz?'), findsNothing);

    await tester.tap(find.text('Tümü'));
    await tester.pumpAndSettle();
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

    // Cam bar icerigin ustunde duruyor; dugmeyi once gorunur alana getir.
    await tester.ensureVisible(find.text('Kasada okut'));
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
      MaterialApp(
        home: Scaffold(
          body: MenuSekmesi(
            kart: hediyeliKart,
            kahveler: DemoVeri.menu,
            yukleniyor: false,
            karta: () {},
          ),
        ),
      ),
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

  test('http gorsel adresi https ye cevrilir', () {
    // Android release derlemesi duz HTTP'yi engelliyor; sunucu bir donem
    // http:// adresler uretiyordu ve hicbir fotograf yuklenmiyordu.
    final urun = KahveUrun.jsondan({
      'id': 1,
      'ad': 'Espresso',
      'fiyat': 70,
      'gorsel': 'http://site.com/media/kahve/a.png',
    });

    expect(urun.gorsel, 'https://site.com/media/kahve/a.png');
  });

  test('https adres oldugu gibi kalir', () {
    final urun = KahveUrun.jsondan({
      'id': 1,
      'ad': 'Latte',
      'fiyat': 80,
      'gorsel': 'https://site.com/media/kahve/b.png',
    });

    expect(urun.gorsel, 'https://site.com/media/kahve/b.png');
  });

  testWidgets('Cok damgada menu seridi tasmaz', (tester) async {
    // Esik 10'a cikinca 11 halka 118px'e sigmiyor ve okunmaz dilimlere
    // donuyordu; o durumda halkalarin yerini ince cubuk aliyor.
    final k = DemoVeri.kartUret(10);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MenuSekmesi(
            kart: k,
            kahveler: DemoVeri.menu,
            yukleniyor: false,
            karta: () {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull, reason: 'tasma olmamali');
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.text('${k.aktifKahve}/10'), findsOneWidget);
  });

  testWidgets('Az damgada halkalar korunur', (tester) async {
    final k = DemoVeri.kartUret(5);

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: MenuSekmesi(
            kart: k,
            kahveler: DemoVeri.menu,
            yukleniyor: false,
            karta: () {},
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(tester.takeException(), isNull);
    expect(find.byType(LinearProgressIndicator), findsNothing);
    expect(find.byType(DamgaSirasi), findsWidgets);
  });
}
