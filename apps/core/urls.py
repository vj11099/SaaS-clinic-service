from django.urls import path, include
from .views.patients import PatientViews
from .views.appointment import AppointmentViews
from .views.documents import DocumentViewSet
from rest_framework import routers

router = routers.DefaultRouter()

router.register(r'patients', PatientViews, basename='patient-detail')
router.register(
    r'appointments',
    AppointmentViews,
    basename='appointment-detail'
)
router.register(r'documents', DocumentViewSet, basename='document')

urlpatterns = [
    path('', include(router.urls)),
]
