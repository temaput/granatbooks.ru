# set encoding=utf-8

"""
Customized product models
"""

from django.db import models
from django.utils.translation import ugettext_lazy as _

from oscar.apps.catalogue.abstract_models import AbstractProduct

class Product(AbstractProduct):
    authors = models.CharField(u'Авторы', max_length=255, blank=True, null=True)

from oscar.apps.catalogue.models import *
