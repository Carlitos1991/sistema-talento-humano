from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from employee.models import Employee
from person.models import Person


class EmployeeActionListViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin',
            email='admin@example.com',
            password='secret123',
        )
        self.client.force_login(self.user)

        for i in range(12):
            person = Person.objects.create(
                first_name=f'Empleado{i}',
                last_name='Prueba',
                document_number=f'12345678{i:02d}',
                email=f'empleado{i}@example.com',
            )
            Employee.objects.create(person=person, is_active=True)

    def test_employee_action_list_is_paginated(self):
        response = self.client.get(reverse('personnel_actions:action_employee_list'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('employees', response.context)
        self.assertEqual(len(response.context['employees']), 10)
        self.assertEqual(response.context['paginator'].count, 12)
