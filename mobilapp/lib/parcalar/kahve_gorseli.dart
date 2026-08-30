import 'package:flutter/material.dart';

import '../tema.dart';

/// Kahve gorseli. Yerel asset ile sunucudan gelen adresi ayni yerde toplar,
/// gorsel yoksa damga halkasi motifine duser.
class KahveGorseli extends StatelessWidget {
  const KahveGorseli({super.key, required this.adres, this.uyum = BoxFit.cover});

  final String adres;
  final BoxFit uyum;

  @override
  Widget build(BuildContext context) {
    if (adres.isEmpty) return const _BosGorsel();

    if (adres.startsWith('assets/')) {
      return Image.asset(adres, fit: uyum, errorBuilder: (_, _, _) => const _BosGorsel());
    }

    return Image.network(
      adres,
      fit: uyum,
      errorBuilder: (_, _, _) => const _BosGorsel(),
      loadingBuilder: (context, cocuk, ilerleme) =>
          ilerleme == null ? cocuk : const _BosGorsel(),
    );
  }
}

class _BosGorsel extends StatelessWidget {
  const _BosGorsel();

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: KahveRenk.espresso3,
      child: Center(
        child: FractionallySizedBox(
          widthFactor: .38,
          child: AspectRatio(
            aspectRatio: 1,
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(color: KahveRenk.crema.withValues(alpha: .28), width: 2),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
