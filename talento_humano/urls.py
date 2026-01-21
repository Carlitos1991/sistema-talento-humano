# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('person/', include('person.urls')),
    path('security/', include('security.urls')),
    path('institution/', include('institution.urls')),
    path('budget/', include('budget.urls')),
    path('employee/', include('employee.urls')),
    path('schedule/', include('schedule.urls')),
    path('contract/', include('contract.urls')),
    path('function_manual/', include('function_manual.urls')),
    path('biometric/', include('biometric.urls')),

]

# Configuración para servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
