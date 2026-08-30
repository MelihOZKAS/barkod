from django.db import migrations, models


def adi_guncelle(apps, schema_editor):
    """Kayitli isim eski varsayilansa yeni markaya cek.

    Kullanici kendi bir isim yazdiysa dokunulmaz.
    """
    KahveAyar = apps.get_model("kahve", "KahveAyar")
    KahveAyar.objects.filter(isletme_adi="Atlas Kahve").update(isletme_adi="Atlas Coffee")


def adi_geri_al(apps, schema_editor):
    KahveAyar = apps.get_model("kahve", "KahveAyar")
    KahveAyar.objects.filter(isletme_adi="Atlas Coffee").update(isletme_adi="Atlas Kahve")


class Migration(migrations.Migration):

    dependencies = [
        ("kahve", "0005_kahvekategori_alter_kahve_options_kahve_kategori"),
    ]

    operations = [
        migrations.AlterField(
            model_name="kahveayar",
            name="isletme_adi",
            field=models.CharField(
                default="Atlas Coffee", max_length=120, verbose_name="İşletme adı"
            ),
        ),
        migrations.RunPython(adi_guncelle, adi_geri_al),
    ]
