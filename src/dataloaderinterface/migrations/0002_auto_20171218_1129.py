# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-12-18 11:29
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dataloaderinterface', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='hydroshareuser',
            old_name='oauth_scope',
            new_name='scope',
        ),
    ]
