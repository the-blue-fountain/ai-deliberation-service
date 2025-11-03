# Final migration to properly set up GraderResponse timestamps

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_add_submitted_at'),
    ]

    operations = [
        # AlterField both to allow nulls temporarily, set defaults, then make NOT NULL
        migrations.AlterField(
            model_name='graderresponse',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AlterField(
            model_name='graderresponse',
            name='submitted_at',
            field=models.DateTimeField(auto_now_add=True),
        ),
    ]
