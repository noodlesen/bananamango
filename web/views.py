from django.shortcuts import render

# Create your views here.

def main(request):
    p = posts
    context = {}
    return render(request, 'web/main.html', context)