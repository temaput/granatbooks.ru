from oscar.apps.dashboard.catalogue.views \
        import ProductCreateUpdateView as CoreProductCreateUpdateView

from forms import ProductForm

class ProductCreateUpdateView(CoreProductCreateUpdateView):
    form_class = ProductForm
