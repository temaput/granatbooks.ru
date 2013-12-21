
from oscar.apps.shipping import repository 
from apps.shipping.methods import (
    Pickup, Express, RusPost)


class Repository(repository.Repository):
    methods = (Pickup, Express, RusPost)

    def get_shipping_methods(self, user, basket, shipping_addr=None, **kwargs):
        methods = super(Repository, self).get_shipping_methods(
                        user, basket, shipping_addr, **kwargs)
        for m in methods:
            if hasattr(m, 'set_shipping_addr'):
                m.set_shipping_addr(shipping_addr)
        return methods


