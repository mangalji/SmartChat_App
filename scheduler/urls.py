from django.urls import path
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

app_name = 'scheduler'

@login_required
def index(request):
    return render(request, 'scheduler/index.html')

urlpatterns = [
    path('', index, name='index'),
]
