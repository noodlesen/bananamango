from django.db import models

# Create your models here.

class Post(models.Model):
    title = models.CharField(max_length=255)
    text = models.TextField(default='', blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    published_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return ('Post: '+self.title)
