# nutrition_tracker/serializers.py
from rest_framework import serializers
from .models import Day, MealEntry

class MealEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = MealEntry
        fields = ['id', 'day', 'text', 'calories', 'protein', 'fat', 'carbs', 'datetime']

class DaySerializer(serializers.ModelSerializer):
    meals = MealEntrySerializer(many=True, read_only=True)

    class Meta:
        model = Day
        fields = [
            'id', 'user', 'date', 'weight', 'activity_description', 'steps',
            'total_calories', 'total_protein', 'total_fat', 'total_carbs', 'meals'
        ]
        read_only_fields = ['total_calories', 'total_protein', 'total_fat', 'total_carbs', 'meals']
