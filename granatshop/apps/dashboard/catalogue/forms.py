from oscar.apps.dashboard.catalogue import forms

class ProductForm(forms.ProductForm):

    class Meta(forms.ProductForm.Meta):
        fields = ('upc', 'title', 'authors', 'description', 'slug', 
                  'related_products', 'parent', 'is_discountable')
        exclude = None

