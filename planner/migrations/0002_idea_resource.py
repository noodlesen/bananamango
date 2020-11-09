# Generated by Django 2.2.17 on 2020-11-09 11:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Idea',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('post_type', models.CharField(choices=[('recipe', 'RECIPE'), ('tip', 'TIP'), ('info', 'INFO'), ('other', 'OTHER')], default='recipe', max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='Resource',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('link', models.URLField()),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('idea', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='planner.Idea')),
            ],
        ),
    ]
