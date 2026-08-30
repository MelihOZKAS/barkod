from django.db import migrations, models


class Migration(migrations.Migration):
    """Borc hareketi aciklamasi uzun metin olsun.

    Borca aktarirken musterinin o gun aldigi urunler de aciklamaya yaziliyor;
    varchar(255) yetmiyordu. PostgreSQL'de varchar -> text donusumu tabloyu
    yeniden yazmaz, anlik ve veri kaybi yoktur.

    ELLE yazildi: ciplak `makemigrations` calistirilirsa Django bunun yaninda
    planlanmamis bir Musteri.Cep_Telefonu degisikligi de uretiyor (modelde
    null=True, migration 0008'de NOT NULL kalmis - onceden var olan uyumsuzluk).
    """

    dependencies = [
        ("stok", "0008_alter_musteri_cep_telefonu_alter_stok_grup"),
    ]

    operations = [
        migrations.AlterField(
            model_name="borchareketi",
            name="aciklama",
            field=models.TextField(),
        ),
    ]
