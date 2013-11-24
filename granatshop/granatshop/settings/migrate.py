from .base import *
from .dev import *

# need to remove theese to prevent south from being to cautious
INSTALLED_APPS.remove('apps.checkout')
INSTALLED_APPS.remove('apps.shipping')
