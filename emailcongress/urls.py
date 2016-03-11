"""emailcongress URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls import url, include
from django.contrib import admin
from django.views.generic.base import RedirectView
from django.conf.urls.static import static

from emailcongress.views import *
from django.views.decorators.cache import cache_page

urlpatterns = [
    # pages
    url(r'^$', IndexView.as_view(), name='index'),
    url(r'^signup', SignupView.as_view(), name='signup'),
    url(r'^complete$', CompleteView.as_view(), name='complete'),
    url(r'^complete/(?P<token>[\w]{64})', CompleteView.as_view(), name='complete-verify'),
    url(r'^validate/(?P<token>[\w]{64})', SignupView.as_view(), name='validate'),
    url(r'^faq', FaqView.as_view(), name='faq'),
    url(r'^admin/', admin.site.urls),
    # actions
    url(r'^ajax/autofill_address', AutofillAddressView.as_view(), name='autofill_address'),
    url(r'^postmark/inbound', PostmarkView.as_view(), name='postmark'),
    # imports
    url(r'^api/', include('api.urls', namespace='api')),
    # catch-all redirects back to home page
    url(r'^.*$', RedirectView.as_view(url='/', permanent=False)),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ]
