# Generated migration for adding description field and AI deliberation models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        # Add description field to DiscussionSession
        migrations.AddField(
            model_name='discussionsession',
            name='description',
            field=models.TextField(blank=True, help_text='Detailed description (rendered as markdown for users)'),
        ),
        # Create AIDeliberationSession model
        migrations.CreateModel(
            name='AIDeliberationSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('s_id', models.CharField(max_length=64, unique=True)),
                ('topic', models.CharField(blank=True, max_length=255)),
                ('description', models.TextField(blank=True, help_text='Detailed session description')),
                ('objective_questions', models.JSONField(blank=True, default=list)),
                ('personas', models.JSONField(blank=True, default=list)),
                ('system_prompt_template', models.TextField(blank=True, help_text='System prompt template (placeholders: {persona}, {question}, {opinions})')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-updated_at', '-id'),
            },
        ),
        # Create AIDebateRun model
        migrations.CreateModel(
            name='AIDebateRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('transcript', models.JSONField(blank=True, default=list)),
                ('completed', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='debate_runs', to='core.aideliberationsession')),
            ],
            options={
                'ordering': ('-created_at',),
            },
        ),
        # Create AIDebateSummary model
        migrations.CreateModel(
            name='AIDebateSummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('topic', models.CharField(blank=True, max_length=255)),
                ('description', models.TextField(blank=True)),
                ('objective_questions', models.JSONField(blank=True, default=list)),
                ('personas', models.JSONField(blank=True, default=list)),
                ('summary_markdown', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('session', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='summary', to='core.aideliberationsession')),
            ],
            options={
                'verbose_name_plural': 'AI Debate Summaries',
            },
        ),
    ]

