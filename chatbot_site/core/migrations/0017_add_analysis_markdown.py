from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_remove_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='gradersession',
            name='analysis_markdown',
            field=models.TextField(blank=True, help_text='LLM-generated analysis of collected grader feedback'),
        ),
    ]
