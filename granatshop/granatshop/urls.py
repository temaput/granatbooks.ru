from django.conf.urls import patterns, include, url
from django.conf import settings
from django.views.generic.base import RedirectView
from django.conf.urls.static import static
from oscar.views import handler500, handler404, handler403

from app import application

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = patterns('',

    # Examples:
        # url(r'^$', RedirectView.as_view(url='/catalogue'), name='home'),
        url(r'', include(application.urls)),
    # url(r'^granatshop/', include('granatshop.foo.urls')),
    
    # Robokassa integration...
    (r'^checkout/robokassa/', include('robokassa.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
        url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
        url(r'^admin/', include(admin.site.urls)),

    # Redirect for Shmeman
        url(r'^[Ss]hmeman/$', RedirectView.as_view(url='/catalogue/shmeman_2')),

)
# Allow rosetta to be used to add translations
if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += patterns('',
        (r'^rosetta/', include('rosetta.urls')),
    )



if settings.DEBUG:
    # Server statics and uploaded media
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
    # Allow error pages to be tested
    urlpatterns += patterns('',
        url(r'^403$', handler403),
        url(r'^404$', handler404),
        url(r'^500$', handler500)
    )
