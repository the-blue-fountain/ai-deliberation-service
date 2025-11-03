# Generated migration to add submitted_at and created_at columns to GraderResponse

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_add_grader_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='graderresponse',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='graderresponse',
            name='submitted_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
    ]
