#set encoding=utf-8
from logging import getLogger
log = getLogger(__name__)

from django.contrib import messages
from django.core.urlresolvers import reverse, reverse_lazy
from django.http import Http404, HttpResponseRedirect, HttpResponseBadRequest
from django.utils.translation import ugettext as _
from django.db.models import get_model

from oscar.core.loading import get_class, get_classes
from oscar.core.compat import get_user_model


from oscar.apps.checkout.views import PaymentMethodView as corePaymentMethodView
from oscar.apps.checkout.views import PaymentDetailsView as corePaymentDetailsView
from oscar.apps.checkout.views import ThankYouView as coreThankYouView

from robokassa.facade import robokassa_redirect

from apps.shipping.methods import Pickup
from apps.shipping.repository import Repository


RedirectRequired, UnableToTakePayment, PaymentError = get_classes(
            'payment.exceptions', ['RedirectRequired', 'UnableToTakePayment', 
                'PaymentError'])

Dispatcher = get_class('customer.utils', 'Dispatcher')
CommunicationEventType = get_model('customer', 'CommunicationEventType')
Order = get_model('order', 'Order')
SourceType = get_model('payment', 'SourceType')
Source = get_model('payment', 'Source')
CheckoutSessionData = get_class('checkout.utils', 'CheckoutSessionData')
# defered payment codes - коды офлайновых способов оплаты, нал, через банк, по счету
DeferedPaymentCodes = ('cash_payment', 'sbrf_slip', 'invoice_payment')

User = get_user_model()

class PaymentMethodView(corePaymentMethodView):
    template_name = 'checkout/payment_methods.html'
    def get(self, request, *args, **kwargs):
        # Check that the user's basket is not empty
        if request.basket.is_empty:
            messages.error(request, _("You need to add some items to your basket to checkout"))
            return HttpResponseRedirect(reverse('basket:summary'))

        shipping_required = request.basket.is_shipping_required()

        # Check that shipping address has been completed
        if shipping_required and not self.checkout_session.is_shipping_address_set():
            messages.error(request, _("Please choose a shipping address"))
            return HttpResponseRedirect(reverse('checkout:shipping-address'))

        # Check that shipping method has been set
        if shipping_required and not self.checkout_session.is_shipping_method_set():
            messages.error(request, _("Please choose a shipping method"))
            return HttpResponseRedirect(reverse('checkout:shipping-method'))

        self._methods = self.get_available_payment_methods()
        # ----------------------------------------------------
        return super(corePaymentMethodView, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        method_code = request.POST.get('method_code', None)
        # Check the validity of method

        # Save the choosen method
        self.checkout_session.pay_by(SourceType.objects.get(code=method_code))

        return self.get_success_response()

    def get_available_payment_methods(self):
        return SourceType.objects.all()

    def get_context_data(self, **kwargs):
        ctx = super(corePaymentMethodView, self).get_context_data(**kwargs)
        ctx['methods'] = self._methods
        return ctx

    def get_success_response(self):
        if self.checkout_session.payment_method().code in DeferedPaymentCodes:
            return HttpResponseRedirect(reverse('checkout:preview'))
        return HttpResponseRedirect(reverse('checkout:payment-details'))


def checkout_session_shipping_method(self, basket=None, shipping_address=None):
    """
    This we inject into checkout_session object, to replace original method
    without rewriting the whole app. Purpose is to pass shipping address to
    Repository, so that we could prime our methods, that require address, i.e
    Russian Post.
    Returns the shipping method model based on the
    data stored in the session.
    """
    log.debug("Injected shipping_method func invoked")
    if not basket:
        basket = self.request.basket
    code = self._get('shipping', 'method_code')
    if not code:
        return None
    return Repository().find_by_code(code, basket, shipping_address)

class PaymentDetailsView(corePaymentDetailsView):
    advice_type_code = 'NEW_ORDER_ADVICE'

    def send_advice_message(self, order):
        """ send advice message about new order to manager """
        code = self.advice_type_code
        ctx = {'user': self.request.user,
               'order': order,
               'lines': order.lines.all()}
        try:
            event_type = CommunicationEventType.objects.get(code=code)
        except CommunicationEventType.DoesNotExist:
            # No event-type in database, attempt to find templates for this
            # type and render them immediately to get the messages.  Since we
            # have not CommunicationEventType to link to, we can't create a
            # CommunicationEvent instance.
            messages = CommunicationEventType.objects.get_and_render(code, ctx)
            event_type = None
        else:
            messages = event_type.get_messages(ctx)

        if messages and messages['body']:
            for manager in User.objects.filter(is_staff=True):  # Here we should pick users from managers group
                if manager.email:
                    dispatcher = Dispatcher()
                    dispatcher.dispatch_direct_messages(manager.email, messages)

    def get_shipping_method(self, basket=None):
        """ this method originaly placed in checkout_session"""
        log.debug("get_shipping_method invokes from View")
        shipping_address = self.get_shipping_address()
        if not hasattr(self.checkout_session, 'shipping_method_injected'):
            import types
            f = types.MethodType(checkout_session_shipping_method, 
                    self.checkout_session, CheckoutSessionData)
            self.checkout_session.shipping_method = f
            self.checkout_session.shipping_method_injected = True
        method = self.checkout_session.shipping_method(basket, shipping_address)

        # We default to using Customer Pickup
        if not method:
            method = Pickup()

        return method

    def handle_successful_order(self, order):
        """ This actually came from OrderPlacement mixin
        --------------------------------------------
        Handle the various steps required after an order has been successfully
        placed.

        Override this view if you want to perform custom actions when an
        order is submitted.
        """
        # Send confirmation message (normally an email)
        self.send_confirmation_message(order)


        # This is custom notification for managers about the new order
        self.send_advice_message(order)  

        # Flush all session data
        self.checkout_session.flush()

        # Save order id in session so thank-you page can load it
        self.request.session['checkout_order_id'] = order.id

        response = HttpResponseRedirect(self.get_success_url())
        self.send_signal(self.request, response, order)
        return response

    def get_context_data(self, **kwargs):
        ctx = super(PaymentDetailsView, self).get_context_data(**kwargs)
        ctx['payment_method'] = self.checkout_session.payment_method()
        ctx.update(kwargs)
        return ctx

    def handle_payment(self, order_number, total_incl_tax, **kwargs):
        source_type = self.checkout_session.payment_method()
        log.debug("=" * 80)
        log.debug("PROCESSING PAYMENT")
        log.debug("=" * 80)
        log.debug("source_type code is %s", source_type.code)
        if not source_type.code in DeferedPaymentCodes:
            log.debug("Not deferred")
            # here we parse the actual online payment
            if source_type.code in ("robokassa",):
                log.debug("Is robokassa")
                if self.request.user.is_superuser:  # ! REMOVE THIS
                    log.debug("User is superuser")
                    # we need to pass basket number and amount
                    basket_num = self.checkout_session.get_submitted_basket_id()
                    # this call supposed to raise RedirectRequiredError
                    robokassa_redirect(basket_num, total_incl_tax, 
                            order_num=order_number)
            raise UnableToTakePayment(u"Данный вид платежа не поддерживается")


        # Request was successful - record the "payment source".  As this
        # request was a 'pre-auth', we set the 'amount_allocated' - if we had
        # performed an 'auth' request, then we would set 'amount_debited'.
        source = Source(source_type=source_type,
                        amount_allocated=total_incl_tax,
                        reference='') # PA: reference could be No of invoice?
        self.add_payment_source(source)

        # Also record payment event
        self.add_payment_event(
            'pre-auth', total_incl_tax, reference='')


class ThankYouView(coreThankYouView):
    """
    Displays the 'thank you' page which summarises the order just submitted.
    """
    template_name = 'checkout/thank_you.html'
    context_object_name = 'order'

    def get_object(self):
        # We allow superusers to force an order thankyou page for testing
        order = None
        if self.request.user.is_superuser:
            if 'order_number' in self.request.GET:
                order = Order._default_manager.get(number=self.request.GET['order_number'])
            elif 'order_id' in self.request.GET:
                order = Order._default_manager.get(id=self.request.GET['order_id'])

        if not order:
            if 'checkout_order_id' in self.request.session:
                order = Order._default_manager.get(pk=self.request.session['checkout_order_id'])
            else:
                raise Http404(_("No order found"))

        return order

    def get_context_data(self, **kwargs):
        ctx = super(ThankYouView, self).get_context_data(**kwargs)
        order = ctx.get("order", None)
        if order:
            payment_method = order.sources.all()[0].source_type
            if payment_method.code in ('sbrf_slip', 'invoice_payment'):
                ctx['print_invoice'] = True
                ctx['payment_method_code'] = payment_method.code
        return ctx
