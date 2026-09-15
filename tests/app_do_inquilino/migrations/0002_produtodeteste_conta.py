import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app_do_inquilino', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='produtodeteste',
            name='conta',
            field=models.ForeignKey(
                db_column='conta_guid',
                help_text='A conta dona desta linha, identificada pelo GUID.',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='+',
                to=settings.AUTH_USER_MODEL,
                to_field='guid',
                verbose_name='conta',
            ),
        ),
    ]
