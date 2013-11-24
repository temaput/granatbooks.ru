from django import forms
from django.conf import settings
from django.db.models import get_model
from django.forms.models import modelformset_factory, BaseModelFormSet
from django.utils.translation import ugettext_lazy as _

from oscar.templatetags.currency_filters import currency

Line = get_model('basket', 'line')
Basket = get_model('basket', 'basket')
Product = get_model('catalogue', 'product')


class AddToBasketForm(forms.Form):
    # We set required=False as validation happens later on
    product_id = forms.IntegerField(widget=forms.HiddenInput(), required=False,
                                    min_value=1, label=_("Product ID"))
    quantity = forms.IntegerField(widget=forms.HiddenInput(), 
                    initial=1, min_value=1, label=_('Quantity'))

    def __init__(self, request, instance, *args, **kwargs):
        super(AddToBasketForm, self).__init__(*args, **kwargs)
        self.request = request
        self.basket = request.basket
        self.instance = instance
        if instance:
            if instance.is_group:
                self._create_group_product_fields(instance)
            else:
                self._create_product_fields(instance)

    def is_purchase_permitted(self, user, product, desired_qty):
        return product.is_purchase_permitted(user=user, quantity=desired_qty)

    def cleaned_options(self):
        """
        Return submitted options in a clean format
        """
        options = []
        for option in self.instance.options:
            if option.code in self.cleaned_data:
                options.append({
                    'option': option,
                    'value': self.cleaned_data[option.code]})
        return options

    def clean(self):
        # Check product exists
        try:
            product = Product.objects.get(
                id=self.cleaned_data.get('product_id', None))
        except Product.DoesNotExist:
            raise forms.ValidationError(
                _("Please select a valid product"))

        # Check user has permission to this the desired quantity to their
        # basket.
        current_qty = self.basket.product_quantity(product)
        desired_qty = current_qty + self.cleaned_data.get('quantity', 1)
        is_permitted, reason = self.is_purchase_permitted(
            self.request.user, product, desired_qty)
        if not is_permitted:
            raise forms.ValidationError(reason)

        return self.cleaned_data

    def clean_quantity(self):
        qty = self.cleaned_data['quantity']
        basket_threshold = settings.OSCAR_MAX_BASKET_QUANTITY_THRESHOLD
        if basket_threshold:
            total_basket_quantity = self.basket.num_items
            max_allowed = basket_threshold - total_basket_quantity
            if qty > max_allowed:
                raise forms.ValidationError(
                    _("Due to technical limitations we are not able to ship"
                      " more than %(threshold)d items in one order. Your"
                      " basket currently has %(basket)d items.") % {
                          'threshold': basket_threshold,
                          'basket': total_basket_quantity,
                      })
        return qty

    def _create_group_product_fields(self, item):
        """
        Adds the fields for a "group"-type product (eg, a parent product with a
        list of variants.

        Currently requires that a stock record exists for the variant
        """
        choices = []
        for variant in item.variants.all():
            if variant.has_stockrecord:
                title = variant.get_title()
                attr_summary = variant.attribute_summary()
                price = currency(variant.stockrecord.price_incl_tax)
                if attr_summary:
                    summary = u"%s (%s) - %s" % (title, attr_summary, price)
                else:
                    summary = u"%s - %s" % (title, price)
                choices.append((variant.id, summary))
                self.fields['product_id'] = forms.ChoiceField(
                    choices=tuple(choices), label=_("Variant"))

    def _create_product_fields(self, item):
        """
        Add the product option fields.
        """
        for option in item.options:
            self._add_option_field(item, option)

    def _add_option_field(self, item, option):
        """
        Creates the appropriate form field for the product option.

        This is designed to be overridden so that specific widgets can be used
        for certain types of options.
        """
        kwargs = {'required': option.is_required}
        self.fields[option.code] = forms.CharField(**kwargs)
