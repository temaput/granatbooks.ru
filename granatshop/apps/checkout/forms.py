from django.db.models import get_model
from oscar.apps.checkout import forms


class ShippingAddressForm(forms.ShippingAddressForm):
    class Meta:
        model = get_model('order', 'shippingaddress')
        exclude = ('user', 'search_text', 'title', 'line3', 'state')
