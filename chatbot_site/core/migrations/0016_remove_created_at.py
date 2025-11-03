# Migration to remove created_at column since submitted_at is sufficient

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0015_fix_timestamps'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='graderresponse',
            name='created_at',
        ),
    ]
