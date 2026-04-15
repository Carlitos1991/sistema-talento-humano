#!/usr/bin/env python3
import os
import sys
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talento_humano.settings')
import django
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from apps.employee.views import EmployeeSelfDashboardView

def run():
    User = get_user_model()
    u = User.objects.filter(is_active=True).first()
    print('USER', u.id if u else None, getattr(u, 'username', None))
    rf = RequestFactory()
    req = rf.get('/employee/self_dashboard/')
    SessionMiddleware().process_request(req)
    req.session.save()
    MessageMiddleware().process_request(req)
    req.user = u
    try:
        view = EmployeeSelfDashboardView.as_view()
        resp = view(req)
        status = getattr(resp, 'status_code', None)
        print('STATUS', status)
        if hasattr(resp, 'render') and callable(resp.render):
            resp.render()
        body = getattr(resp, 'content', b'')
        print('BODY_HEAD')
        try:
            print(body[:2000].decode('utf-8', errors='replace'))
        except Exception:
            print(body[:2000])
    except Exception:
        print('\n--- TRACEBACK ---')
        traceback.print_exc()

if __name__ == '__main__':
    run()
