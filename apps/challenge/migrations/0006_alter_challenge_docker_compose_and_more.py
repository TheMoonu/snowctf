# Generated by Django 5.1.6 on 2025-04-22 11:13

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('challenge', '0005_remove_challenge_deployment_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='challenge',
            name='docker_compose',
            field=models.ForeignKey(blank=True, help_text='选择Docker容器配置', null=True, on_delete=django.db.models.deletion.SET_NULL, to='challenge.dockercompose', verbose_name='容器配置'),
        ),
        migrations.AlterField(
            model_name='challenge',
            name='static_files',
            field=models.ForeignKey(blank=True, help_text='选择要使用的题目附件', null=True, on_delete=django.db.models.deletion.SET_NULL, to='challenge.staticfile', verbose_name='题目附件'),
        ),
    ]
