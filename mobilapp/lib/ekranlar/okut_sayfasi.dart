import 'package:barcode_widget/barcode_widget.dart';
import 'package:flutter/material.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../modeller/kart.dart';
import '../tema.dart';

/// Kasada okutma ekrani. Tam ekran ve beyaz: okuyucu kodu en kolay boyle yakalar.
class OkutSayfasi extends StatelessWidget {
  const OkutSayfasi({super.key, required this.kart});

  final Kart kart;

  static Route<void> yol(Kart kart) => PageRouteBuilder<void>(
        opaque: false,
        barrierColor: Colors.black54,
        transitionDuration: const Duration(milliseconds: 320),
        pageBuilder: (_, _, _) => OkutSayfasi(kart: kart),
        transitionsBuilder: (_, canlandirma, _, cocuk) {
          final egri = CurvedAnimation(parent: canlandirma, curve: Curves.easeOutCubic);
          return FadeTransition(
            opacity: egri,
            child: SlideTransition(
              position: Tween(begin: const Offset(0, .06), end: Offset.zero).animate(egri),
              child: cocuk,
            ),
          );
        },
      );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: KahveRenk.porselen,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(Aralik.b3),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('KASADA OKUT', style: etiketStili(renk: const Color(0xFF6E6158))),
                        const SizedBox(height: 4),
                        Text(
                          kart.adSoyad,
                          style: baslikStili(boyut: 22, renk: KahveRenk.espresso, aralik: -.6),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close),
                    color: KahveRenk.espresso,
                    tooltip: 'Kapat',
                  ),
                ],
              ),

              Expanded(
                child: Center(
                  child: SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        LayoutBuilder(
                          builder: (context, kisit) {
                            final olcu = (kisit.maxWidth * .82).clamp(200.0, 320.0);
                            return QrImageView(
                              data: kart.kod,
                              version: QrVersions.auto,
                              size: olcu,
                              padding: EdgeInsets.zero,
                              eyeStyle: const QrEyeStyle(
                                eyeShape: QrEyeShape.square,
                                color: KahveRenk.espresso,
                              ),
                              dataModuleStyle: const QrDataModuleStyle(
                                dataModuleShape: QrDataModuleShape.square,
                                color: KahveRenk.espresso,
                              ),
                            );
                          },
                        ),
                        const SizedBox(height: Aralik.b5),
                        BarcodeWidget(
                          barcode: Barcode.code128(),
                          data: kart.kod,
                          drawText: false,
                          height: 76,
                          color: KahveRenk.espresso,
                        ),
                        const SizedBox(height: Aralik.b2),
                        Text(
                          kart.kod.replaceAllMapped(RegExp(r'.{3}'), (e) => '${e.group(0)} ').trim(),
                          style: veriStili(boyut: 17, renk: const Color(0xFF6E6158), aralik: 3),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.light_mode_outlined, size: 17, color: Color(0xFF8A7A6D)),
                  const SizedBox(width: 6),
                  Text(
                    'Okunmazsa ekran parlaklığını artırın',
                    style: TextStyle(fontSize: 13, color: KahveRenk.espresso.withValues(alpha: .5)),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
