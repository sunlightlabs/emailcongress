from django.conf.urls import url, include
from api import views
from rest_framework import routers


router = routers.DefaultRouter()
router.register(r'^users', views.UserViewSet)
router.register(r'^legislators', views.LegislatorViewSet)
router.register(r'^messages', views.MessageViewSet)

urlpatterns = [
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    url(r'^', include(router.urls)),
]
