import 'dart:ui';

import 'package:flutter/material.dart';

import '../tema.dart';

/// Alt navigasyon: cam (buzlu) zemin uzerinde iki sekme.
/// Icerik barin altindan aktigi icin Scaffold'da extendBody: true olmali.
class CamBar extends StatelessWidget {
  const CamBar({super.key, required this.kartAcik, required this.sekmeSecildi});

  final bool kartAcik;
  final ValueChanged<bool> sekmeSecildi;

  @override
  Widget build(BuildContext context) {
    final altBosluk = MediaQuery.paddingOf(context).bottom;

    return ClipRect(
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 24, sigmaY: 24),
        child: Container(
          padding: EdgeInsets.fromLTRB(Aralik.b3, Aralik.b2, Aralik.b3,
              (altBosluk > 0 ? altBosluk - 2 : Aralik.b2)),
          decoration: BoxDecoration(
            color: KahveRenk.espresso.withValues(alpha: .72),
            border: Border(
              top: BorderSide(color: KahveRenk.porselen.withValues(alpha: .10)),
            ),
          ),
          child: Row(
            children: [
              Expanded(
                child: _Sekme(
                  etiket: 'Menü',
                  simge: kartAcik ? Icons.local_cafe_outlined : Icons.local_cafe,
                  secili: !kartAcik,
                  dokunma: () => sekmeSecildi(false),
                ),
              ),
              const SizedBox(width: Aralik.b1),
              Expanded(
                child: _Sekme(
                  etiket: 'Kartım',
                  simge: kartAcik ? Icons.qr_code_2 : Icons.qr_code_2_outlined,
                  secili: kartAcik,
                  dokunma: () => sekmeSecildi(true),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _Sekme extends StatelessWidget {
  const _Sekme({
    required this.etiket,
    required this.simge,
    required this.secili,
    required this.dokunma,
  });

  final String etiket;
  final IconData simge;
  final bool secili;
  final VoidCallback dokunma;

  @override
  Widget build(BuildContext context) {
    final renk = secili ? const Color(0xFF2A1B0C) : KahveRenk.porselen.withValues(alpha: .68);
    return Material(
      color: secili ? KahveRenk.crema : Colors.transparent,
      borderRadius: BorderRadius.circular(999),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: dokunma,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 11),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(simge, size: 20, color: renk),
              const SizedBox(width: 8),
              Text(
                etiket,
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: renk),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Menunun ustundeki yatay kategori seridi.
class KategoriSeridi extends StatelessWidget {
  const KategoriSeridi({
    super.key,
    required this.kategoriler,
    required this.secili,
    required this.secildi,
  });

  final List<String> kategoriler;
  final String? secili;
  final ValueChanged<String?> secildi;

  @override
  Widget build(BuildContext context) {
    if (kategoriler.isEmpty) return const SizedBox.shrink();

    return SizedBox(
      height: 40,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: Aralik.b3),
        children: [
          _Cip(etiket: 'Tümü', secili: secili == null, dokunma: () => secildi(null)),
          for (final k in kategoriler) ...[
            const SizedBox(width: Aralik.b1),
            _Cip(etiket: k, secili: secili == k, dokunma: () => secildi(k)),
          ],
        ],
      ),
    );
  }
}

class _Cip extends StatelessWidget {
  const _Cip({required this.etiket, required this.secili, required this.dokunma});

  final String etiket;
  final bool secili;
  final VoidCallback dokunma;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: secili ? KahveRenk.crema : KahveRenk.porselen.withValues(alpha: .07),
      borderRadius: BorderRadius.circular(999),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: dokunma,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
          child: Center(
            child: Text(
              etiket,
              style: TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
                color: secili ? const Color(0xFF2A1B0C) : KahveRenk.porselen.withValues(alpha: .72),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
