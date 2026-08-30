import 'package:flutter/material.dart';

import '../demo_veri.dart';
import '../modeller/kart.dart';
import '../parcalar/damga_halkasi.dart';
import '../servis/ayarlar.dart';
import '../tema.dart';
import 'ana_ekran.dart';
import 'okut_sayfasi.dart';

/// Kartim sekmesi: sadakat karti, kasada okutma ve sayaclar.
class ProfilSekmesi extends StatelessWidget {
  const ProfilSekmesi({super.key, required this.kart, this.ayarlar = Ayarlar.varsayilan});

  final Kart kart;
  final Ayarlar ayarlar;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: EdgeInsets.fromLTRB(
          Aralik.b3, Aralik.b4, Aralik.b3,
          MediaQuery.paddingOf(context).bottom + 92,   // cam barin altinda kalmasin
        ),
        children: [
          SekmeBasligi(
            etiket: 'KARTIM',
            baslik: kart.adSoyad,
            sag: kart.bekleyenHediye > 0
                ? Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: _Rozet(
                      metin: '${kart.bekleyenHediye} HEDİYE',
                      renk: KahveRenk.ciniAcik,
                      zemin: KahveRenk.cini.withValues(alpha: .22),
                    ),
                  )
                : null,
          ),
          const SizedBox(height: Aralik.b3),

          SadakatKarti(kart: kart, isletmeAdi: ayarlar.isletmeAdi),
          const SizedBox(height: Aralik.b2),

          FilledButton.icon(
            onPressed: () => Navigator.of(context).push(OkutSayfasi.yol(kart)),
            icon: const Icon(Icons.qr_code_2, size: 22),
            label: const Text('Kasada okut'),
          ),

          const SizedBox(height: Aralik.b5),
          Text('ÖZET', style: etiketStili()),
          const SizedBox(height: Aralik.b2),
          _Sayaclar(kart: kart),

          const SizedBox(height: Aralik.b3),
          _KuralNotu(esik: kart.esik, gun: ayarlar.gecerlilikGun),
        ],
      ),
    );
  }
}

/// Cuzdandan cikarilan fiziksel damga kartinin karsiligi.
class SadakatKarti extends StatelessWidget {
  const SadakatKarti({
    super.key,
    required this.kart,
    this.isletmeAdi = DemoVeri.isletmeAdi,
    this.kompakt = false,
  });

  final Kart kart;
  final String isletmeAdi;
  final bool kompakt;

  @override
  Widget build(BuildContext context) {
    final damgalar = <({DamgaDurumu durum, String? etiket})>[
      for (final d in kart.damgalar)
        (
          durum: d.dolu ? (d.sonuyor ? DamgaDurumu.sonuyor : DamgaDurumu.dolu) : DamgaDurumu.bos,
          etiket: d.sonuyor ? '${d.kalanGun}g' : null,
        ),
      (durum: DamgaDurumu.hediye, etiket: null),
    ];

    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(Yuvarlaklik.l),
        border: Border.all(color: KahveRenk.crema.withValues(alpha: .22)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: .38),
            blurRadius: 32,
            offset: const Offset(0, 14),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(
        children: [
          // cekirdek dokusu: karta sicaklik verir, okumayi bozmaz
          Positioned.fill(
            child: Opacity(
              opacity: .16,
              child: Image.asset('assets/gorseller/cekirdek.jpg', fit: BoxFit.cover),
            ),
          ),
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                  colors: [
                    KahveRenk.espresso2.withValues(alpha: .90),
                    KahveRenk.espresso3.withValues(alpha: .96),
                  ],
                ),
              ),
            ),
          ),
          // kartin ust kenarindaki krema serisi
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: Container(
              height: 3,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [KahveRenk.crema, Color(0x33D69A4C), Colors.transparent],
                ),
              ),
            ),
          ),

          Padding(
            padding: const EdgeInsets.fromLTRB(Aralik.b3, Aralik.b3 + 3, Aralik.b3, Aralik.b3),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // kart basligi
                Row(
                  children: [
                    Container(
                      width: 22,
                      height: 22,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        border: Border.all(color: KahveRenk.crema, width: 1.5),
                        borderRadius: const BorderRadius.all(Radius.elliptical(11, 10)),
                      ),
                      child: Text(
                        isletmeAdi.characters.first,
                        style: baslikStili(boyut: 10, renk: KahveRenk.crema, aralik: 0),
                      ),
                    ),
                    const SizedBox(width: Aralik.b1),
                    Text(isletmeAdi.toUpperCase(), style: etiketStili()),
                    const Spacer(),
                    Text(
                      'SADAKAT KARTI',
                      style: etiketStili(renk: KahveRenk.porselen.withValues(alpha: .32)),
                    ),
                  ],
                ),
                const SizedBox(height: Aralik.b4),

                // sayac
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text(
                      '${kart.aktifKahve}',
                      style: baslikStili(boyut: 52, renk: KahveRenk.crema, aralik: -2.4),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      '/ ${kart.esik}',
                      style: baslikStili(
                        boyut: 20,
                        renk: KahveRenk.porselen.withValues(alpha: .3),
                        aralik: -.4,
                      ),
                    ),
                    const SizedBox(width: Aralik.b2),
                    Text('DAMGA', style: etiketStili()),
                  ],
                ),
                const SizedBox(height: Aralik.b3),

                DamgaSirasi(damgalar: damgalar),
                const SizedBox(height: Aralik.b3),

                Divider(color: KahveRenk.porselen.withValues(alpha: .1), height: 1),
                const SizedBox(height: Aralik.b2),

                Row(
                  children: [
                    Expanded(
                      child: Text(
                        switch (kart) {
                          _ when kart.bekleyenHediye > 0 => 'Sıradaki kahven bizden.',
                          _ when kart.kalan == 1 => 'Bir kahve daha, sonraki bizden.',
                          _ => 'Hediye kahveye ${kart.kalan} kahve kaldı.',
                        },
                        style: TextStyle(
                          fontSize: 14.5,
                          color: KahveRenk.porselen.withValues(alpha: .7),
                        ),
                      ),
                    ),
                    Text(
                      kart.kod,
                      style: veriStili(
                        boyut: 11,
                        renk: KahveRenk.porselen.withValues(alpha: .3),
                        aralik: 1.4,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Sayaclar extends StatelessWidget {
  const _Sayaclar({required this.kart});

  final Kart kart;

  @override
  Widget build(BuildContext context) {
    final kutular = <({String baslik, String deger, Color renk})>[
      (baslik: 'Toplam içtiğin', deger: '${kart.toplamIcim}', renk: KahveRenk.porselen),
      (baslik: 'Kartta bekleyen', deger: '${kart.aktifKahve}', renk: KahveRenk.crema),
      (baslik: 'Hediyeye kalan', deger: '${kart.kalan}', renk: KahveRenk.cremaAcik),
      (baslik: 'Bekleyen hediye', deger: '${kart.bekleyenHediye}', renk: KahveRenk.ciniAcik),
    ];

    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: Aralik.b2,
      crossAxisSpacing: Aralik.b2,
      childAspectRatio: 1.9,
      children: [
        for (final k in kutular)
          Container(
            padding: const EdgeInsets.all(Aralik.b2),
            decoration: BoxDecoration(
              color: KahveRenk.espresso2,
              borderRadius: BorderRadius.circular(Yuvarlaklik.m),
              border: Border.all(color: KahveRenk.porselen.withValues(alpha: .08)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(k.deger, style: baslikStili(boyut: 28, renk: k.renk, aralik: -1)),
                const SizedBox(height: 2),
                Text(
                  k.baslik,
                  style: TextStyle(
                    fontSize: 13,
                    color: KahveRenk.porselen.withValues(alpha: .55),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}

class _KuralNotu extends StatelessWidget {
  const _KuralNotu({required this.esik, required this.gun});

  final int esik;
  final int gun;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(Aralik.b3),
      decoration: BoxDecoration(
        color: KahveRenk.cini.withValues(alpha: .12),
        borderRadius: BorderRadius.circular(Yuvarlaklik.m),
        border: Border.all(color: KahveRenk.ciniAcik.withValues(alpha: .25)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.schedule, size: 20, color: KahveRenk.ciniAcik),
          const SizedBox(width: Aralik.b2),
          Expanded(
            child: Text(
              'Her damga $gun gün kartta kalır. Süresi dolan damga karttan düşer, '
              'yerine yeni kahvelerin geçer. $esik damga dolunca sıradaki kahve bizden.',
              style: TextStyle(
                fontSize: 13.5,
                height: 1.5,
                color: KahveRenk.porselen.withValues(alpha: .72),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Rozet extends StatelessWidget {
  const _Rozet({required this.metin, required this.renk, required this.zemin});

  final String metin;
  final Color renk;
  final Color zemin;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: zemin,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: renk.withValues(alpha: .35)),
      ),
      child: Text(metin, style: veriStili(boyut: 10, renk: renk, aralik: 1.2)),
    );
  }
}
