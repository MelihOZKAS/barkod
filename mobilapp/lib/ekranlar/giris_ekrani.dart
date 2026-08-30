import 'package:flutter/material.dart';

import '../parcalar/damga_halkasi.dart';
import '../servis/ayarlar.dart';
import '../tema.dart';
import 'ana_ekran.dart';

/// Giris ekrani. Firebase henuz bagli degil: buton dogrudan ana ekrani acar.
/// Firebase eklendiginde `_girisYap` icinde token alinip
/// KahveApi.oturumAc(idToken) cagrilacak.
class GirisEkrani extends StatefulWidget {
  const GirisEkrani({super.key});

  @override
  State<GirisEkrani> createState() => _GirisEkraniState();
}

class _GirisEkraniState extends State<GirisEkrani> {
  bool _yukleniyor = false;
  Ayarlar _ayarlar = Ayarlar.simdiki;

  @override
  void initState() {
    super.initState();
    // Ayarlari erkenden cek: ana ekran acildiginda hazir olsun.
    Ayarlar.getir().then((a) {
      if (mounted) setState(() => _ayarlar = a);
    });
  }

  Future<void> _girisYap() async {
    setState(() => _yukleniyor = true);
    await Future<void>.delayed(const Duration(milliseconds: 420));
    if (!mounted) return;

    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        transitionDuration: const Duration(milliseconds: 460),
        pageBuilder: (_, _, _) => const AnaEkran(),
        transitionsBuilder: (_, canlandirma, _, cocuk) {
          final egri = CurvedAnimation(parent: canlandirma, curve: Curves.easeOutCubic);
          return FadeTransition(
            opacity: egri,
            child: SlideTransition(
              position: Tween(begin: const Offset(0, .03), end: Offset.zero).animate(egri),
              child: cocuk,
            ),
          );
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Espresso akiyor: dukkanin en tanidik ani.
          Image.asset('assets/gorseller/giris.jpg', fit: BoxFit.cover),

          // Metnin okunmasi icin asagidan yukari koyulasan perde
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0xB31C1411),
                  Color(0x661C1411),
                  Color(0xE81C1411),
                  KahveRenk.espresso,
                ],
                stops: [0, .34, .68, 1],
              ),
            ),
          ),

          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(Aralik.b3, Aralik.b3, Aralik.b3, Aralik.b3),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Marka(ad: _ayarlar.isletmeAdi),
                  const Spacer(),

                  Text('SADAKAT KARTI', style: etiketStili()),
                  const SizedBox(height: Aralik.b2),
                  Text(
                    'Kartın seni\nbekliyor.',
                    style: baslikStili(boyut: 42, aralik: -1.6, satirYuksekligi: 1.05),
                  ),
                  const SizedBox(height: Aralik.b2),
                  Text(
                    'Her kahve karta bir damga bırakır. '
                    '${_ayarlar.hediyeIcinKahve} damga dolunca sıradaki kahve bizden.',
                    style: TextStyle(
                      fontSize: 15.5,
                      height: 1.5,
                      color: KahveRenk.porselen.withValues(alpha: .74),
                    ),
                  ),

                  const SizedBox(height: Aralik.b4),
                  const DamgaSirasi(
                    aralik: 12,
                    damgalar: [
                      (durum: DamgaDurumu.dolu, etiket: null),
                      (durum: DamgaDurumu.dolu, etiket: null),
                      (durum: DamgaDurumu.dolu, etiket: null),
                      (durum: DamgaDurumu.bos, etiket: null),
                      (durum: DamgaDurumu.bos, etiket: null),
                      (durum: DamgaDurumu.hediye, etiket: null),
                    ],
                  ),
                  const SizedBox(height: Aralik.b5),

                  FilledButton(
                    onPressed: _yukleniyor ? null : _girisYap,
                    child: _yukleniyor
                        ? const SizedBox(
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2.4,
                              color: Color(0xFF2A1B0C),
                            ),
                          )
                        : const Text('Giriş yap'),
                  ),
                  const SizedBox(height: Aralik.b2),
                  Center(
                    child: Text(
                      'Firebase girişi bir sonraki adımda bağlanacak',
                      style: TextStyle(
                        fontSize: 12.5,
                        color: KahveRenk.porselen.withValues(alpha: .4),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Marka extends StatelessWidget {
  const _Marka({required this.ad});

  final String ad;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 38,
          height: 38,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: KahveRenk.espresso.withValues(alpha: .45),
            border: Border.all(color: KahveRenk.crema, width: 2),
            borderRadius: const BorderRadius.all(Radius.elliptical(19, 18)),
          ),
          child: Text(
            ad.characters.first,
            style: baslikStili(boyut: 16, renk: KahveRenk.crema, aralik: 0),
          ),
        ),
        const SizedBox(width: Aralik.b1 + 2),
        Text(ad, style: baslikStili(boyut: 18, aralik: -.4)),
      ],
    );
  }
}
