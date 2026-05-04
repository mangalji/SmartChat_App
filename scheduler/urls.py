from django.urls import path
from django.shortcuts import render

app_name = 'scheduler'

def index(request):
    return render(request, 'scheduler/index.html')

urlpatterns = [
    path('', index, name='index'),
]
