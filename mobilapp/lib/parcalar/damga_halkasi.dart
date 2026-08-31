import 'dart:math';

import 'package:flutter/material.dart';

import '../tema.dart';

/// Imza bileseni: kahve fincaninin biraktigi halka.
/// Web tarafindaki damga kartinin mobil karsiligi.
enum DamgaDurumu { bos, dolu, sonuyor, hediye }

class DamgaHalkasi extends StatelessWidget {
  const DamgaHalkasi({
    super.key,
    required this.durum,
    this.etiket,
    this.olcu = 76,
    this.tohum = 0,
  });

  final DamgaDurumu durum;
  final String? etiket;
  final double olcu;
  final int tohum;

  @override
  Widget build(BuildContext context) {
    final donme = ((tohum % 3) - 1) * 0.055;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Transform.rotate(
          angle: donme,
          child: SizedBox(
            width: olcu,
            height: olcu,
            child: CustomPaint(
              painter: _HalkaBoyayici(durum: durum, tohum: tohum),
              child: durum == DamgaDurumu.hediye
                  ? Center(
                      child: Icon(
                        Icons.local_cafe_outlined,
                        size: olcu * .3,
                        color: KahveRenk.ciniAcik,
                      ),
                    )
                  : null,
            ),
          ),
        ),
        SizedBox(
          height: 22,
          child: etiket == null
              ? null
              : Padding(
                  padding: const EdgeInsets.only(top: Aralik.b1),
                  child: Text(
                    etiket!,
                    style: veriStili(
                      boyut: 10,
                      renk: switch (durum) {
                        DamgaDurumu.sonuyor => const Color(0xFFE8A48F),
                        DamgaDurumu.hediye => KahveRenk.ciniAcik,
                        _ => KahveRenk.porselen.withValues(alpha: .42),
                      },
                    ),
                  ),
                ),
        ),
      ],
    );
  }
}

class _HalkaBoyayici extends CustomPainter {
  _HalkaBoyayici({required this.durum, required this.tohum});

  final DamgaDurumu durum;
  final int tohum;

  @override
  void paint(Canvas tuval, Size boyut) {
    final merkez = Offset(boyut.width / 2, boyut.height / 2);
    final yariCap = min(boyut.width, boyut.height) / 2 - 2;
    final yol = _dalgaliCember(merkez, yariCap, tohum, .045);

    final dolu = durum == DamgaDurumu.dolu || durum == DamgaDurumu.sonuyor;
    final cizgiRengi = switch (durum) {
      DamgaDurumu.dolu => KahveRenk.crema,
      DamgaDurumu.sonuyor => KahveRenk.uyari,
      DamgaDurumu.hediye => KahveRenk.ciniAcik,
      DamgaDurumu.bos => KahveRenk.porselen.withValues(alpha: .16),
    };

    if (dolu) {
      // fincanin biraktigi leke: disa dogru koyulasan halka
      final leke = Paint()
        ..shader = RadialGradient(
          colors: [
            Colors.transparent,
            cizgiRengi.withValues(alpha: .14),
            cizgiRengi.withValues(alpha: .34),
            Colors.transparent,
          ],
          stops: const [.56, .60, .76, .80],
        ).createShader(Rect.fromCircle(center: merkez, radius: yariCap));
      tuval.drawPath(yol, leke);

      // ic gollenme
      tuval.drawPath(
        _dalgaliCember(merkez, yariCap * .58, tohum + 7, .07),
        Paint()..color = cizgiRengi.withValues(alpha: .13),
      );
    }

    final kalem = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = dolu ? 2.5 : 2
      ..color = cizgiRengi;

    // bos ve hediye slotlari kesikli: henuz basilmamis damga
    tuval.drawPath(dolu ? yol : _kesikli(yol, 6, 5), kalem);
  }

  /// Elle basilmis izlenimi icin hafif bozulmus cember.
  Path _dalgaliCember(Offset merkez, double yariCap, int tohum, double bozulma) {
    final rastgele = Random(tohum);
    const adet = 8;
    final noktalar = <Offset>[
      for (var i = 0; i < adet; i++)
        () {
          final aci = (i / adet) * 2 * pi;
          final r = yariCap * (1 + (rastgele.nextDouble() - .5) * bozulma);
          return merkez + Offset(cos(aci) * r, sin(aci) * r);
        }(),
    ];

    Offset orta(Offset a, Offset b) => Offset((a.dx + b.dx) / 2, (a.dy + b.dy) / 2);

    final yol = Path();
    final baslangic = orta(noktalar[adet - 1], noktalar[0]);
    yol.moveTo(baslangic.dx, baslangic.dy);
    for (var i = 0; i < adet; i++) {
      final simdiki = noktalar[i];
      final sonraki = noktalar[(i + 1) % adet];
      final o = orta(simdiki, sonraki);
      yol.quadraticBezierTo(simdiki.dx, simdiki.dy, o.dx, o.dy);
    }
    yol.close();
    return yol;
  }

  Path _kesikli(Path kaynak, double cizgi, double bosluk) {
    final hedef = Path();
    for (final olcum in kaynak.computeMetrics()) {
      var mesafe = 0.0;
      while (mesafe < olcum.length) {
        final son = min(mesafe + cizgi, olcum.length);
        hedef.addPath(olcum.extractPath(mesafe, son), Offset.zero);
        mesafe = son + bosluk;
      }
    }
    return hedef;
  }

  @override
  bool shouldRepaint(_HalkaBoyayici eski) => eski.durum != durum || eski.tohum != tohum;
}

/// Damgalarin sirayla basilmasi.
class DamgaSirasi extends StatelessWidget {
  const DamgaSirasi({
    super.key,
    required this.damgalar,
    this.olcu,
    this.canlandir = true,
    this.aralik = 10,
    this.enKucuk = 34,
    this.enBuyuk = 78,
  });

  final List<({DamgaDurumu durum, String? etiket})> damgalar;

  /// Verilmezse damgalar tek sirada kalacak sekilde genislige gore olculur.
  final double? olcu;
  final bool canlandir;
  final double aralik;

  /// Otomatik olcumun alt ve ust siniri.
  final double enKucuk;
  final double enBuyuk;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, kisit) {
        final sigan = (kisit.maxWidth - (aralik * (damgalar.length - 1))) / damgalar.length;
        // enKucuk bir ALT SINIR degil, tercih edilen en kucuk olcu. Sigmiyorsa
        // ona zorlamak satiri tasiriyor ve halkalar okunmaz dilimlere donuyordu.
        final tercih = olcu ?? sigan.clamp(enKucuk, enBuyuk);
        return _siraCiz(context, sigan > 0 ? tercih.clamp(0.0, sigan) : tercih);
      },
    );
  }

  Widget _siraCiz(BuildContext context, double halkaOlcusu) {
    final hareketAcik = canlandir && !MediaQuery.disableAnimationsOf(context);

    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        for (var i = 0; i < damgalar.length; i++)
          TweenAnimationBuilder<double>(
            tween: Tween(begin: hareketAcik ? 0 : 1, end: 1),
            duration: Duration(milliseconds: hareketAcik ? 420 : 0),
            curve: Interval(
              (i * .09).clamp(0.0, .7),
              1,
              curve: Curves.easeOutBack,
            ),
            builder: (context, deger, cocuk) => Opacity(
              opacity: deger.clamp(0.0, 1.0),
              child: Transform.scale(scale: .7 + (deger * .3), child: cocuk),
            ),
            child: DamgaHalkasi(
              durum: damgalar[i].durum,
              etiket: damgalar[i].etiket,
              olcu: halkaOlcusu,
              tohum: i,
            ),
          ),
      ],
    );
  }
}
