import 'package:flutter/material.dart';

import '../modeller/kart.dart';
import '../parcalar/cam_bar.dart';
import '../parcalar/damga_halkasi.dart';
import '../parcalar/kahve_gorseli.dart';
import '../tema.dart';
import 'ana_ekran.dart';

class MenuSekmesi extends StatelessWidget {
  const MenuSekmesi({
    super.key,
    required this.kart,
    required this.kahveler,
    required this.yukleniyor,
    required this.karta,
    this.kategoriAdi,
    this.kategoriler = const [],
    this.kategoriSecildi,
    this.canliVeri = true,
  });

  final Kart kart;
  final List<KahveUrun> kahveler;
  final bool yukleniyor;

  /// false ise sunucuya ulasilamadi, ekranda demo veri var.
  final bool canliVeri;

  final List<String> kategoriler;
  final ValueChanged<String?>? kategoriSecildi;

  /// Ustteki seritten secilen kategori. null ise tum menu gosterilir.
  final String? kategoriAdi;

  /// Ilerleme seridine dokununca Kartim sekmesine gecer.
  final VoidCallback karta;

  @override
  Widget build(BuildContext context) {
    final hediyeVar = kart.bekleyenHediye > 0;
    // Alt bar cam oldugu icin icerik onun altindan akiyor; son kart gizlenmesin.
    final altBosluk = MediaQuery.paddingOf(context).bottom + 92;

    return SafeArea(
      bottom: false,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(Aralik.b3, Aralik.b4, Aralik.b3, Aralik.b3),
            child: SekmeBasligi(
              etiket: kategoriAdi == null ? 'MENÜ' : kategoriAdi!.toUpperCase(),
              baslik: kategoriAdi ?? 'Bugün ne içiyoruz?',
              sag: yukleniyor
                  ? null
                  : Padding(
                      padding: const EdgeInsets.only(bottom: 6),
                      child: Text(
                        '${kahveler.length} ürün',
                        style: veriStili(boyut: 12, renk: KahveRenk.kabuk),
                      ),
                    ),
            ),
          ),

          // Kategoriler urunlerin ustunde, yatay kayan serit halinde
          if (kategoriSecildi != null)
            KategoriSeridi(
              kategoriler: kategoriler,
              secili: kategoriAdi,
              secildi: kategoriSecildi!,
            ),

          Expanded(
            child: ListView(
              padding: EdgeInsets.fromLTRB(Aralik.b3, Aralik.b3, Aralik.b3, altBosluk),
              children: [
                if (!canliVeri && !yukleniyor) ...[
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: KahveRenk.uyari.withValues(alpha: .14),
                      borderRadius: BorderRadius.circular(Yuvarlaklik.s),
                      border: Border.all(color: KahveRenk.uyari.withValues(alpha: .35)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.cloud_off_outlined, size: 17, color: Color(0xFFE8A48F)),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Sunucuya ulaşılamadı — örnek menü gösteriliyor.',
                            style: TextStyle(
                                fontSize: 13, color: KahveRenk.porselen.withValues(alpha: .8)),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: Aralik.b3),
                ],

                // Kart durumu menude de gorunsun: kac kahve kaldigini bilerek secersin.
                _IlerlemeSeridi(kart: kart, karta: karta),
                const SizedBox(height: Aralik.b3),

                if (yukleniyor)
                  ...List.generate(3, (_) => const _Iskelet())
                else if (kahveler.isEmpty)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: Aralik.b5),
                    child: Center(
                      child: Text(
                        'Bu bölümde henüz ürün yok.',
                        style: TextStyle(color: KahveRenk.porselen.withValues(alpha: .5)),
                      ),
                    ),
                  )
                else
                  ...kahveler.map(
                    (k) => _KahveKarti(
                        kahve: k, hediyeIleAlinabilir: hediyeVar && k.hediyeGecerli),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Damga sayisi cok oldugunda seritteki halkalarin yerini alan ince cubuk.
class _MiniIlerleme extends StatelessWidget {
  const _MiniIlerleme({required this.dolu, required this.esik, required this.hediyeVar});

  final int dolu;
  final int esik;
  final bool hediyeVar;

  @override
  Widget build(BuildContext context) {
    final oran = esik > 0 ? (dolu / esik).clamp(0.0, 1.0) : 0.0;
    final renk = hediyeVar ? KahveRenk.ciniAcik : KahveRenk.crema;

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: LinearProgressIndicator(
            value: hediyeVar ? 1.0 : oran,
            minHeight: 8,
            backgroundColor: KahveRenk.porselen.withValues(alpha: .10),
            valueColor: AlwaysStoppedAnimation(renk),
          ),
        ),
        const SizedBox(height: 6),
        Text(
          hediyeVar ? 'hazır' : '$dolu/$esik',
          style: veriStili(boyut: 11, renk: KahveRenk.kabuk),
        ),
      ],
    );
  }
}

/// Menunun ustundeki ince kart ozeti.
class _IlerlemeSeridi extends StatelessWidget {
  const _IlerlemeSeridi({required this.kart, required this.karta});

  final Kart kart;
  final VoidCallback karta;

  @override
  Widget build(BuildContext context) {
    final hediyeVar = kart.bekleyenHediye > 0;

    final damgalar = <({DamgaDurumu durum, String? etiket})>[
      for (final d in kart.damgalar)
        (
          durum: d.dolu ? (d.sonuyor ? DamgaDurumu.sonuyor : DamgaDurumu.dolu) : DamgaDurumu.bos,
          etiket: null,
        ),
      (durum: DamgaDurumu.hediye, etiket: null),
    ];

    return Material(
      color: hediyeVar ? KahveRenk.cini.withValues(alpha: .16) : KahveRenk.espresso2,
      borderRadius: BorderRadius.circular(Yuvarlaklik.m),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: karta,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: Aralik.b3, vertical: Aralik.b2),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(Yuvarlaklik.m),
            border: Border.all(
              color: hediyeVar
                  ? KahveRenk.ciniAcik.withValues(alpha: .35)
                  : KahveRenk.porselen.withValues(alpha: .08),
            ),
          ),
          child: Row(
            children: [
              // Dar seritte 11 halka okunmaz dilimlere donuyordu. Halkalar
              // ancak sigdiginda; sigmiyorsa ince bir ilerleme cubugu.
              // Tam halka sirasi zaten Kartim sekmesinde duruyor.
              SizedBox(
                width: 118,
                child: damgalar.length <= 7
                    ? DamgaSirasi(
                        aralik: 4,
                        enKucuk: 12,
                        enBuyuk: 17,
                        canlandir: false,
                        damgalar: damgalar,
                      )
                    : _MiniIlerleme(
                        dolu: kart.aktifKahve,
                        esik: kart.esik,
                        hediyeVar: hediyeVar,
                      ),
              ),
              const SizedBox(width: Aralik.b2),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      hediyeVar
                          ? 'Bir kahve hediye'
                          : '${kart.aktifKahve} / ${kart.esik} damga',
                      style: baslikStili(
                        boyut: 16,
                        renk: hediyeVar ? KahveRenk.ciniAcik : KahveRenk.porselen,
                        aralik: -.4,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      hediyeVar
                          ? 'Aşağıdan seç, kasada söyle'
                          : '${kart.kalan} kahve sonra hediye',
                      style: TextStyle(
                        fontSize: 12.5,
                        color: KahveRenk.porselen.withValues(alpha: .55),
                      ),
                    ),
                  ],
                ),
              ),
              Icon(
                Icons.chevron_right,
                size: 20,
                color: KahveRenk.porselen.withValues(alpha: .35),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _KahveKarti extends StatelessWidget {
  const _KahveKarti({required this.kahve, required this.hediyeIleAlinabilir});

  final KahveUrun kahve;
  final bool hediyeIleAlinabilir;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: Aralik.b3),
      decoration: BoxDecoration(
        color: KahveRenk.espresso2,
        borderRadius: BorderRadius.circular(Yuvarlaklik.l),
        border: Border.all(
          color: hediyeIleAlinabilir
              ? KahveRenk.ciniAcik.withValues(alpha: .38)
              : KahveRenk.porselen.withValues(alpha: .08),
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: .28),
            blurRadius: 24,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      clipBehavior: Clip.antiAlias,
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () {},
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Stack(
                children: [
                  AspectRatio(
                    aspectRatio: 1,   // tum gorseller 1:1
                    child: KahveGorseli(adres: kahve.gorsel),
                  ),
                  Positioned.fill(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.center,
                          end: Alignment.bottomCenter,
                          colors: [Colors.transparent, Colors.black.withValues(alpha: .55)],
                        ),
                      ),
                    ),
                  ),
                  if (hediyeIleAlinabilir)
                    Positioned(
                      left: Aralik.b2,
                      top: Aralik.b2,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                        decoration: BoxDecoration(
                          color: KahveRenk.cini.withValues(alpha: .92),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          'HEDİYENLE ALABİLİRSİN',
                          style: veriStili(boyut: 10, renk: KahveRenk.porselen, aralik: 1),
                        ),
                      ),
                    ),
                  Positioned(
                    right: Aralik.b2,
                    bottom: Aralik.b2,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                      decoration: BoxDecoration(
                        color: KahveRenk.espresso.withValues(alpha: .82),
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(color: KahveRenk.crema.withValues(alpha: .45)),
                      ),
                      child: Text(
                        '${kahve.fiyat.toStringAsFixed(0)} ₺',
                        style: veriStili(boyut: 14, agirlik: FontWeight.w600),
                      ),
                    ),
                  ),
                ],
              ),
              Padding(
                padding: const EdgeInsets.all(Aralik.b3),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(kahve.ad, style: baslikStili(boyut: 21, aralik: -.6)),
                    if (kahve.aciklama.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        kahve.aciklama,
                        style: TextStyle(
                          fontSize: 14.5,
                          height: 1.45,
                          color: KahveRenk.porselen.withValues(alpha: .64),
                        ),
                      ),
                    ],
                    if (kahve.icindekiler.isNotEmpty) ...[
                      const SizedBox(height: Aralik.b2),
                      Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          for (final madde in kahve.icindekiler)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 5),
                              decoration: BoxDecoration(
                                color: KahveRenk.porselen.withValues(alpha: .06),
                                borderRadius: BorderRadius.circular(999),
                              ),
                              child: Text(
                                madde,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: KahveRenk.porselen.withValues(alpha: .6),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Iskelet extends StatelessWidget {
  const _Iskelet();

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 320,
      margin: const EdgeInsets.only(bottom: Aralik.b3),
      decoration: BoxDecoration(
        color: KahveRenk.porselen.withValues(alpha: .05),
        borderRadius: BorderRadius.circular(Yuvarlaklik.l),
      ),
    );
  }
}
