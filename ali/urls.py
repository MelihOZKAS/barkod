"""
URL configuration for ali project.

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
from django.urls import path,include,re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as medya_servisi

urlpatterns = [
    path("admin/", admin.site.urls),
    path("kahve/", include("kahve.urls")),
    # Admin'den yuklenen gorseller DEBUG kapaliyken de servis edilsin.
    # Onunde /media/ location'i olan bir nginx varsa istek buraya hic ulasmaz.
    re_path(r"^media/(?P<path>.*)$", medya_servisi, {"document_root": settings.MEDIA_ROOT}),
    path("", include("stok.urls")),
]+ static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
