import logging
log = logging.getLogger(__name__)

from decimal import Decimal as D
from oscar.apps.shipping import repository 
from oscar.apps.shipping.methods import OfferDiscount, NoShippingRequired
from apps.shipping.methods import (
    Pickup, Express, RusPost)


class Repository(repository.Repository):
    methods = (Pickup(), Express(D('300'), D('300')), RusPost(D('400')))

    def get_shipping_methods(self, user, basket, shipping_addr=None, **kwargs):
        log.debug("Repository knows about following shipping methods: %s", 
                    self.prime_methods(basket, shipping_addr, self.methods))
        return self.prime_methods(basket, shipping_addr, self.methods)

    def prime_methods(self, basket, shipping_addr, methods):
        """
        Prime a list of shipping method instances

        This involves injecting the basket instance into each and adding any
        discount wrappers.
        """
        return [self.prime_method(basket, shipping_addr, method) for
                method in methods]

    def prime_method(self, basket, shipping_addr, method):
        """
        Prime an individual method instance
        """
        log.debug("Injecting basket to shipping method: %s ...", method)
        method.set_basket(basket)
        if hasattr(method, 'set_shipping_addr'):
            method.set_shipping_addr(shipping_addr)
        # If the basket has a shipping offer, wrap the shipping method with a
        # decorating class that applies the offer discount to the shipping
        # charge.
        if basket.offer_applications.shipping_discounts:
            # We assume there is only one shipping discount available
            discount = basket.offer_applications.shipping_discounts[0]
            if method.basket_charge_incl_tax > D('0.00'):
                return OfferDiscount(method, discount['offer'])
        log.debug("...complete: returning method as %s", method)
        return method

    def find_by_code(self, code, basket, shipping_addr=None):
        """
        Return the appropriate Method object for the given code
        """
        for method in self.methods:
            if method.code == code:
                return self.prime_method(basket, shipping_addr, method)

        # Check for NoShippingRequired as that is a special case
        if code == NoShippingRequired.code:
            return self.prime_method(basket, NoShippingRequired())

