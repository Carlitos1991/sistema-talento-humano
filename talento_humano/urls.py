# config/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.views.generic import TemplateView
from django.views.static import serve

from biometric import adms_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('person/', include('person.urls')),
    path('security/', include('security.urls')),
    path('institution/', include('institution.urls')),
    path('budget/', include('budget.urls')),
    path('payroll/', include('payroll.urls')),
    path('permitrequest/', include('permitrequest.urls')),
    path('employee/', include('employee.urls')),
    path('schedule/', include('schedule.urls')),
    path('contract/', include('contract.urls')),
    path('personnel_actions/', include('personnel_actions.urls')),
    path('function_manual/', include('function_manual.urls')),
    path('biometric/', include('biometric.urls')),
    path('iclock/cdata', adms_views.adms_receive_attendance),

]

# Configuración para servir archivos MEDIA (fotos, documentos, etc.)
# Funciona tanto con DEBUG=True como DEBUG=False en desarrollo
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

# Rutas de prueba solo en desarrollo
if settings.DEBUG:
    # Rutas para probar páginas de error en desarrollo
    urlpatterns += [
        path('test-404/', TemplateView.as_view(template_name='404.html')),
        path('test-403/', TemplateView.as_view(template_name='403.html')),
        path('test-500/', TemplateView.as_view(template_name='500.html')),
    ]

# Manejadores de errores personalizados
handler404 = 'core.views.custom_page_not_found'
handler403 = 'core.views.custom_permission_denied'
handler500 = 'core.views.custom_server_error'
