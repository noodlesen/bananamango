from django.contrib import admin
from planner.models import Post, Idea, Resource

# Register your models here.


class PostAdmin(admin.ModelAdmin):
    list_display = ('title', 'scheduled_date', 'published_date')

admin.site.register(Post, PostAdmin)

class IdeaAdmin(admin.ModelAdmin):
    list_display = ('title', 'post_type')

admin.site.register(Idea, IdeaAdmin)

admin.site.register(Resource)