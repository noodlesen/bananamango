# nutrition_tracker/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DayViewSet, MealEntryViewSet

router = DefaultRouter()
router.register(r'days', DayViewSet, basename='day')
router.register(r'meals', MealEntryViewSet, basename='meal')

urlpatterns = [
    path('api/', include(router.urls)),
]
