# nutrition_tracker/models.py
from django.conf import settings
from django.db import models

class Day(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    weight = models.FloatField(null=True, blank=True)
    activity_description = models.TextField(blank=True)
    steps = models.IntegerField(null=True, blank=True)

    total_calories = models.FloatField(default=0)
    total_protein = models.FloatField(default=0)
    total_fat = models.FloatField(default=0)
    total_carbs = models.FloatField(default=0)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def recalc_totals(self):
        meals = self.meals.all()  # type: ignore
        self.total_calories = sum(m.calories or 0 for m in meals)
        self.total_protein = sum(m.protein or 0 for m in meals)
        self.total_fat = sum(m.fat or 0 for m in meals)
        self.total_carbs = sum(m.carbs or 0 for m in meals)
        self.save()

    def get_remaining(self, targets: dict):
        """
        targets = {'calories': 2000, 'protein': 150, 'fat': 70, 'carbs': 250}
        """
        return {
            'calories': targets.get('calories', 0) - self.total_calories,
            'protein': targets.get('protein', 0) - self.total_protein,
            'fat': targets.get('fat', 0) - self.total_fat,
            'carbs': targets.get('carbs', 0) - self.total_carbs,
        }

class MealEntry(models.Model):
    day = models.ForeignKey(Day, related_name='meals', on_delete=models.CASCADE)
    text = models.TextField()
    calories = models.FloatField(null=True, blank=True)
    protein = models.FloatField(null=True, blank=True)
    fat = models.FloatField(null=True, blank=True)
    carbs = models.FloatField(null=True, blank=True)
    datetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['datetime']
