from oscar.apps.checkout import app
from oscar.core.loading import get_class

from apps.checkout import views

class CheckoutApplication(app.CheckoutApplication):
    payment_method_view = views.PaymentMethodView
    payment_details_view = views.PaymentDetailsView
    thankyou_view = views.ThankYouView


application = CheckoutApplication()
