"""
URL configuration for visualiser project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from plot_visualisation.views import index, plot_view, plot_api, plot_age_bar, plot_umap, plot_trend
from plot_visualisation import urls as faceSender_urls

urlpatterns = [
    path("admin/", admin.site.urls),
    path('', index, name='index'),
    path(r'qc/', include(faceSender_urls)),
    path('plot/', plot_view, name='plot'),
    path('api/plot/bar', plot_api, name='plot_api'),  # Expose the API endpoint at /api/plot/
    path('api/plot/age_bar/', plot_age_bar, name='plot_age_bar'),
    path('api/plot/umap/', plot_umap, name='plot_umap'),
    path('api/plot/trend/', plot_trend, name='plot_trend'),
]
