# Generated migration to add user_instructions field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0011_add_description_and_ai_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='discussionsession',
            name='user_instructions',
            field=models.TextField(
                blank=True,
                help_text='Optional moderator-provided instructions for participants',
            ),
        ),
        migrations.AddField(
            model_name='aideliberationsession',
            name='user_instructions',
            field=models.TextField(
                blank=True,
                help_text='Optional moderator-provided instructions for AI agents',
            ),
        ),
    ]
