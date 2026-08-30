import 'package:flutter/material.dart';

import '../demo_veri.dart';
import '../modeller/kart.dart';
import '../parcalar/cam_bar.dart';
import '../servis/api.dart';
import '../servis/ayarlar.dart';
import '../servis/yapilandirma.dart';
import '../tema.dart';
import 'menu_sekmesi.dart';
import 'profil_sekmesi.dart';

/// Ana ekran. Menu ve ayarlar sunucudan gelir; kart Firebase baglanana kadar
/// demodur ama esigi sunucudaki gercek kurala gore kurulur.
///
/// Alt bar cam efektli ve kategorileri gosterir; icerik onun altindan aksin
/// diye Scaffold extendBody: true.
class AnaEkran extends StatefulWidget {
  const AnaEkran({super.key});

  @override
  State<AnaEkran> createState() => _AnaEkranState();
}

class _AnaEkranState extends State<AnaEkran> {
  bool _kartAcik = false;
  String? _seciliKategori;

  Ayarlar _ayarlar = Ayarlar.simdiki;
  late Kart _kart = DemoVeri.kartUret(_ayarlar.hediyeIcinKahve);

  List<KahveUrun> _menu = const [];
  bool _menuYukleniyor = true;

  /// Veri sunucudan mi geldi? false ise demo gosteriyoruz — kullanici bilsin.
  bool _canliVeri = false;

  @override
  void initState() {
    super.initState();
    _ayarlariGetir();
    _menuyuGetir();
  }

  Future<void> _ayarlariGetir() async {
    final a = await Ayarlar.getir();
    if (!mounted) return;
    setState(() {
      _ayarlar = a;
      _kart = DemoVeri.kartUret(a.hediyeIcinKahve);
    });
  }

  Future<void> _menuyuGetir() async {
    List<KahveUrun> gelen;
    var canli = false;
    if (!Yapilandirma.bagli) {
      gelen = DemoVeri.menu;
    } else {
      try {
        gelen = await KahveApi().menu();
        canli = true;
      } on Object {
        // Sunucuya ulasilamadi. Bos ekran gostermek yerine demo veriyle
        // devam ediyoruz ama bunu ekranda belirtiyoruz — sessizce demo
        // gostermek gercek arizayi gizler.
        gelen = DemoVeri.menu;
      }
    }
    if (!mounted) return;
    setState(() {
      _menu = gelen;
      _canliVeri = canli;
      _menuYukleniyor = false;
    });
  }

  /// Menudeki kategoriler, sunucudan geldigi sirayla (tekrarsiz).
  List<String> get _kategoriler {
    final gorulen = <String>[];
    for (final u in _menu) {
      final k = u.kategori.trim();
      if (k.isNotEmpty && !gorulen.contains(k)) gorulen.add(k);
    }
    return gorulen;
  }

  List<KahveUrun> get _gosterilecek {
    if (_seciliKategori == null) return _menu;
    return _menu.where((u) => u.kategori.trim() == _seciliKategori).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBody: true,
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 240),
        switchInCurve: Curves.easeOutCubic,
        transitionBuilder: (cocuk, canlandirma) => FadeTransition(
          opacity: canlandirma,
          child: SlideTransition(
            position: Tween(begin: const Offset(0, .015), end: Offset.zero).animate(canlandirma),
            child: cocuk,
          ),
        ),
        child: _kartAcik
            ? ProfilSekmesi(key: const ValueKey('profil'), kart: _kart, ayarlar: _ayarlar)
            : MenuSekmesi(
                key: ValueKey('menu-${_seciliKategori ?? "tumu"}'),
                kart: _kart,
                kahveler: _gosterilecek,
                yukleniyor: _menuYukleniyor,
                kategoriAdi: _seciliKategori,
                kategoriler: _kategoriler,
                kategoriSecildi: (k) => setState(() => _seciliKategori = k),
                canliVeri: _canliVeri || !Yapilandirma.bagli,
                karta: () => setState(() => _kartAcik = true),
              ),
      ),
      bottomNavigationBar: CamBar(
        kartAcik: _kartAcik,
        sekmeSecildi: (kart) => setState(() => _kartAcik = kart),
      ),
    );
  }
}

/// Iki sekmede de kullanilan ust baslik.
class SekmeBasligi extends StatelessWidget {
  const SekmeBasligi({super.key, required this.etiket, required this.baslik, this.sag});

  final String etiket;
  final String baslik;
  final Widget? sag;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(etiket, style: etiketStili()),
              const SizedBox(height: 6),
              Text(baslik, style: baslikStili(boyut: 30, aralik: -1)),
            ],
          ),
        ),
        ?sag,
      ],
    );
  }
}
