# Generated by Django 2.2.17 on 2020-11-10 21:13

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0002_idea_resource'),
    ]

    operations = [
        migrations.AddField(
            model_name='idea',
            name='is_ready',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='resource',
            name='idea',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='planner.Idea'),
        ),
        migrations.AlterField(
            model_name='resource',
            name='title',
            field=models.CharField(default='Noname', max_length=255),
        ),
    ]
