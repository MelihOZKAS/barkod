"""Raf etiketi alanlari: birim, uretim yeri, fiyat degisim tarihi.

Django bu dosyayi uretirken yanina "Alter field Cep_Telefonu on musteri"
operasyonunu da koydu; o, stok/models.py ile migration 0008 arasinda yillardir
duran bir uyumsuzluk (model null=True diyor, tablo NOT NULL). Bizim isimizle
ilgisi yok, canli musteri tablosuna dokunuyor, bu yuzden ELLE SILINDI --
0009, 0010 ve 0011'de de ayni sey yapildi.

Var olan urunlerin F.D.T. alani bos kalmasin diye guncelleme_tarihi'nden
dolduruluyor: bildigimiz en yakin gercek. Fiyat bundan sonra her degistiginde
Stok.save() tarihi kendisi tazeliyor.
"""

from django.db import migrations, models
from django.db.models.functions import TruncDate


def fiyat_tarihini_doldur(apps, schema_editor):
    Stok = apps.get_model("stok", "Stok")
    Stok.objects.filter(fiyat_tarihi__isnull=True).update(
        fiyat_tarihi=TruncDate("guncelleme_tarihi")
    )


def geri_al(apps, schema_editor):
    # Alanlar zaten kaldirilacak; ayrica temizlemeye gerek yok.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("stok", "0011_satis_indirim"),
    ]

    operations = [
        migrations.AddField(
            model_name="stok",
            name="birim",
            field=models.CharField(
                blank=True,
                default="AD",
                help_text="Etikete basilan birim: AD, KG, MT, PK...",
                max_length=8,
                verbose_name="Birim",
            ),
        ),
        migrations.AddField(
            model_name="stok",
            name="fiyat_tarihi",
            field=models.DateField(
                blank=True,
                help_text="Etiketteki F.D.T. Tutar her değiştiğinde kendiliğinden bugüne çekilir.",
                null=True,
                verbose_name="Fiyat değişim tarihi",
            ),
        ),
        migrations.AddField(
            model_name="stok",
            name="uretim_yeri",
            field=models.CharField(
                blank=True,
                help_text="Etikete basılır. Boş bırakılırsa satır boş çıkar.",
                max_length=60,
                verbose_name="Üretim yeri",
            ),
        ),
        migrations.RunPython(fiyat_tarihini_doldur, geri_al),
    ]
