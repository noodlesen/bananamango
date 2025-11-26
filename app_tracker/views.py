# nutrition_tracker/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone
from .models import Day, MealEntry
from .serializers import DaySerializer, MealEntrySerializer
from .utils import analyze_meal_text


class DayViewSet(viewsets.ModelViewSet):
    serializer_class = DaySerializer

    def get_queryset(self):
        return Day.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'])
    def today(self, request):
        today = timezone.now().date()
        day, created = Day.objects.get_or_create(user=request.user, date=today)
        serializer = self.get_serializer(day)
        return Response(serializer.data)

class MealEntryViewSet(viewsets.ModelViewSet):
    serializer_class = MealEntrySerializer
    
    

    def get_queryset(self):
        return MealEntry.objects.filter(day__user=self.request.user)


    def perform_create(self, serializer):
        meal = serializer.save()
        kbju = analyze_meal_text(meal.text)
        meal.calories = kbju["calories"]
        meal.protein = kbju["protein"]
        meal.fat = kbju["fat"]
        meal.carbs = kbju["carbs"]
        meal.save()
        meal.day.recalc_totals()