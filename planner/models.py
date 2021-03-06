from django.db import models

# Create your models here.

class Post(models.Model):
    title = models.CharField(max_length=255)
    text = models.TextField(default='', blank=True)
    scheduled_date = models.DateField(null=True, blank=True)
    published_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return ('Post: '+self.title)

class Idea(models.Model):
    def __str__(self):
        return self.title
    title = models.CharField(max_length=255, verbose_name='Название')
    description = models.TextField(default='', blank=True, verbose_name='Описание')
    is_ready = models.BooleanField(default=False, verbose_name='Готово')
    POST_TYPES = (
        ('recipe', 'RECIPE',),
        ('tip', 'TIP',),
        ('info', 'INFO'),
        ('other', 'OTHER')
    )
    post_type = models.CharField(max_length=255, choices=POST_TYPES, default='recipe')

    class Meta:
        verbose_name = 'Идея'
        verbose_name_plural = 'Идеи'

    # def get_status(self):
    #     return self.is_ready
    # get_status.short_description = 'Готово'

class Resource(models.Model):
    def __str__(self):
        return self.title
    link = models.URLField()
    idea = models.ForeignKey(Idea, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=255, default='Noname')
    description = models.TextField(null=True, blank=True)
