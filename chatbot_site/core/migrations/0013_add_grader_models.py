# Generated migration for adding grader session and response models

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_add_user_instructions'),
    ]

    operations = [
        # Create GraderSession model
        migrations.CreateModel(
            name='GraderSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('s_id', models.CharField(max_length=64, unique=True)),
                ('topic', models.CharField(blank=True, max_length=255)),
                ('description', models.TextField(blank=True, help_text='Detailed session description (rendered as markdown)')),
                ('objective_questions', models.JSONField(blank=True, default=list)),
                ('knowledge_base', models.TextField(blank=True)),
                ('rag_chunk_count', models.PositiveIntegerField(default=0)),
                ('rag_last_built_at', models.DateTimeField(blank=True, null=True)),
                ('user_instructions', models.TextField(blank=True, help_text='Optional moderator-provided instructions for graders')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ('-updated_at', '-id'),
            },
        ),
        # Create GraderResponse model
        migrations.CreateModel(
            name='GraderResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.PositiveIntegerField()),
                ('scores', models.JSONField(blank=True, default=list)),
                ('reasons', models.JSONField(blank=True, default=list)),
                ('additional_comments', models.TextField(blank=True)),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='responses', to='core.gradersession')),
            ],
            options={
                'ordering': ('-submitted_at',),
            },
        ),
        # Add unique constraint for GraderResponse
        migrations.AddConstraint(
            model_name='graderresponse',
            constraint=models.UniqueConstraint(fields=('session', 'user_id'), name='unique_grader_response_per_user'),
        ),
    ]
