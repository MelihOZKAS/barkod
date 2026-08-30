"""Firebase ID token dogrulama.

firebase-admin paketi kurmadan calisir: token dogrudan Google'in
Identity Toolkit servisine sorulur, cevap Google tarafindan imzalanmis
kullanici bilgisidir. Boylece canli sunucuya yeni bir bagimlilik girmez
(sadece requests, o da zaten requirements.txt icinde).
"""

import requests

LOOKUP_URL = "https://identitytoolkit.googleapis.com/v1/accounts:lookup"


class FirebaseHatasi(Exception):
    pass


def token_dogrula(id_token, api_key, zaman_asimi=10):
    """Gecerliyse kullanici sozlugu doner, degilse FirebaseHatasi firlatir."""
    if not api_key:
        raise FirebaseHatasi("Firebase Web API Key admin panelinde tanimli degil.")
    if not id_token:
        raise FirebaseHatasi("Token gonderilmedi.")

    try:
        cevap = requests.post(
            LOOKUP_URL,
            params={"key": api_key},
            json={"idToken": id_token},
            timeout=zaman_asimi,
        )
    except requests.RequestException as hata:
        raise FirebaseHatasi(f"Firebase'e ulasilamadi: {hata}")

    if cevap.status_code != 200:
        try:
            mesaj = cevap.json().get("error", {}).get("message", cevap.text[:200])
        except ValueError:
            mesaj = cevap.text[:200]
        raise FirebaseHatasi(f"Token dogrulanamadi: {mesaj}")

    kullanicilar = cevap.json().get("users") or []
    if not kullanicilar:
        raise FirebaseHatasi("Token gecerli ama kullanici bulunamadi.")

    k = kullanicilar[0]
    return {
        "uid": k.get("localId"),
        "email": k.get("email", "") or "",
        "ad_soyad": k.get("displayName", "") or "",
        "telefon": k.get("phoneNumber", "") or "",
        "foto": k.get("photoUrl", "") or "",
    }
