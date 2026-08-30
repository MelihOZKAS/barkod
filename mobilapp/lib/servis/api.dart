import 'dart:convert';

import 'package:http/http.dart' as http;

import '../modeller/kart.dart';
import 'yapilandirma.dart';

/// Django tarafindaki kahve modulunun mobil API'si.
/// Her istek 'X-Kahve-Key' basligi tasir; anahtar admin panelinden yonetilir.
class KahveApi {
  KahveApi({http.Client? istemci}) : _istemci = istemci ?? http.Client();

  final http.Client _istemci;

  Map<String, String> _basliklar({String? idToken}) => {
        'X-Kahve-Key': Yapilandirma.apiAnahtari,
        'Content-Type': 'application/json',
        if (idToken != null) 'Authorization': 'Bearer $idToken',
      };

  Uri _adres(String yol) => Uri.parse('${Yapilandirma.sunucu}/kahve/api/v1/$yol');

  Future<Map<String, dynamic>> _al(String yol, {String? idToken}) async {
    final cevap = await _istemci
        .get(_adres(yol), headers: _basliklar(idToken: idToken))
        .timeout(const Duration(seconds: 12));
    final govde = jsonDecode(utf8.decode(cevap.bodyBytes)) as Map<String, dynamic>;
    if (cevap.statusCode != 200 || govde['ok'] != true) {
      throw ApiHatasi(govde['hata']?.toString() ?? 'Sunucuya ulasilamadi (${cevap.statusCode}).');
    }
    return govde;
  }

  Future<List<KahveUrun>> menu() async {
    final govde = await _al('menu/');
    return (govde['kahveler'] as List)
        .map((k) => KahveUrun.jsondan(k as Map<String, dynamic>))
        .toList();
  }

  Future<Map<String, dynamic>> ayarlar() => _al('ayarlar/');

  Future<Kart> kart(String idToken) async {
    final govde = await _al('kart/', idToken: idToken);
    return Kart.jsondan(govde['musteri'] as Map<String, dynamic>);
  }

  /// Firebase ile giris yapildiktan sonra musteri kaydini acar/getirir.
  Future<Kart> oturumAc(String idToken) async {
    final cevap = await _istemci
        .post(_adres('oturum/'), headers: _basliklar(), body: jsonEncode({'id_token': idToken}))
        .timeout(const Duration(seconds: 12));
    final govde = jsonDecode(utf8.decode(cevap.bodyBytes)) as Map<String, dynamic>;
    if (cevap.statusCode != 200 || govde['ok'] != true) {
      throw ApiHatasi(govde['hata']?.toString() ?? 'Giris tamamlanamadi.');
    }
    return Kart.jsondan(govde['musteri'] as Map<String, dynamic>);
  }
}

class ApiHatasi implements Exception {
  const ApiHatasi(this.mesaj);
  final String mesaj;

  @override
  String toString() => mesaj;
}
