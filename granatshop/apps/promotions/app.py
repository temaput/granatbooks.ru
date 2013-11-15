from oscar.apps.promotions.app import PromotionsApplication as oscar_promotions
from apps.promotions.views import HomeView

class PromotionsApplication(oscar_promotions): pass

application = PromotionsApplication()

