import os

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.generic import ListView, View

from budget.models import BudgetModificationHistory
from core.models import CatalogItem
from employee.models import Employee
from person.models import Person
from institution.models import AdministrativeUnit
from schedule.models import Schedule
from .forms import LaborRegimeForm, ContractTypeForm
from .models import LaborRegime, ContractType, ManagementPeriod, History


class LaborRegimeListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LaborRegime
    template_name = 'contract/labor_regime_list.html'
    permission_required = 'contract.view_laborregime'
    context_object_name = 'regimes'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = LaborRegime.objects.all()
        context['stats_total'] = qs.count()
        context['stats_active'] = qs.filter(is_active=True).count()
        context['stats_inactive'] = qs.filter(is_active=False).count()
        return context


class LaborRegimeTablePartialView(LoginRequiredMixin, View):
    def get(self, request):
        name = request.GET.get('name', '')
        is_active = request.GET.get('is_active', '')
        queryset = LaborRegime.objects.all().order_by('code')

        if name: queryset = queryset.filter(name__icontains=name)
        if is_active == 'true':
            queryset = queryset.filter(is_active=True)
        elif is_active == 'false':
            queryset = queryset.filter(is_active=False)

        all_qs = LaborRegime.objects.all()
        stats = {
            'total': all_qs.count(),
            'active': all_qs.filter(is_active=True).count(),
            'inactive': all_qs.filter(is_active=False).count(),
        }

        html = render_to_string('contract/partials/partial_labor_regime_table.html', {
            'regimes': queryset
        }, request=request)
        return JsonResponse({'table_html': html, 'stats': stats})


class LaborRegimeDetailAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        regime = get_object_or_404(LaborRegime, pk=pk)
        return JsonResponse({
            'success': True,
            'regime': {
                'id': regime.id,
                'code': regime.code,
                'name': regime.name,
                'description': regime.description or '',
                'is_active': regime.is_active
            }
        })


class ContractTypeListView(LoginRequiredMixin, View):
    """
    Retorna los tipos de contrato vinculados a un régimen laboral específico.
    """

    def get(self, request, regime_id):
        regime = get_object_or_404(LaborRegime, pk=regime_id)
        types = regime.contract_types.all().order_by('name')

        data = [{
            'id': t.id,
            'code': t.code,
            'name': t.name,
            'category': t.contract_type_category,
            'category_display': t.get_contract_type_category_display(),
            'is_active': t.is_active
        } for t in types]

        return JsonResponse({'success': True, 'contract_types': data})


class ContractTypeCreateView(LoginRequiredMixin, View):
    """
    Crea un nuevo tipo de contrato vinculado a un régimen.
    Diseñado para ser llamado vía AJAX desde SweetAlert2.
    """

    def post(self, request):
        form = ContractTypeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.created_by = request.user
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Modalidad laboral registrada con éxito.'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error interno: {str(e)}'
                }, status=500)

        # Enviamos los errores de validación (ej: código duplicado)
        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class ContractTypeToggleStatusView(LoginRequiredMixin, View):
    """
    Alterna el estado activo/inactivo de una modalidad.
    """

    def post(self, request, pk):
        instance = get_object_or_404(ContractType, pk=pk)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save()
        return JsonResponse({
            'success': True,
            'message': f'Estado de "{instance.name}" actualizado.'
        })


class LaborRegimeCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa la creación de un nuevo régimen laboral."""
    permission_required = 'contract.add_laborregime'

    def post(self, request):
        form = LaborRegimeForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.created_by = request.user  # Auditoría BaseModel
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Régimen Laboral creado exitosamente.'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al guardar: {str(e)}'
                }, status=500)

        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class LaborRegimeUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa la actualización de un régimen existente."""
    permission_required = 'contract.change_laborregime'

    def post(self, request, pk):
        instance = get_object_or_404(LaborRegime, pk=pk)
        form = LaborRegimeForm(request.POST, instance=instance)

        if form.is_valid():
            try:
                with transaction.atomic():
                    updated_instance = form.save(commit=False)
                    updated_instance.updated_by = request.user  # Auditoría BaseModel
                    updated_instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Régimen Laboral actualizado correctamente.'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'message': f'Error al actualizar: {str(e)}'
                }, status=500)

        return JsonResponse({
            'success': False,
            'errors': form.errors
        }, status=400)


class LaborRegimeToggleStatusView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Alterna el estado is_active (Alta/Baja) de un régimen."""
    permission_required = 'contract.change_laborregime'

    def post(self, request, pk):
        instance = get_object_or_404(LaborRegime, pk=pk)
        # Cambiamos el estado (Toggle logic)
        instance.is_active = not instance.is_active
        instance.updated_by = request.user
        instance.save()

        message = "Régimen activado (Alta)" if instance.is_active else "Régimen desactivado (Baja)"
        return JsonResponse({
            'success': True,
            'message': message
        })


class ContractTypeUpdateView(LoginRequiredMixin, View):
    """
    Actualiza un tipo de contrato existente.
    """

    def post(self, request, pk):
        instance = get_object_or_404(ContractType, pk=pk)
        form = ContractTypeForm(request.POST, instance=instance)
        if form.is_valid():
            try:
                with transaction.atomic():
                    instance = form.save(commit=False)
                    instance.updated_by = request.user
                    instance.save()
                return JsonResponse({
                    'success': True,
                    'message': 'Modalidad actualizada correctamente.'
                })
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)

        return JsonResponse({'success': False, 'errors': form.errors}, status=400)


class ManagementPeriodListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManagementPeriod
    template_name = 'contract/management_period_list.html'
    permission_required = 'contract.view_managementperiod'
    context_object_name = 'periods'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = ManagementPeriod.objects.filter(is_active=True)

        # Estadísticas dinámicas: realizar en una sola agregación para reducir consultas
        aggs = qs.aggregate(
            total_active=Count('id'),
            count_losep=Count('id', filter=Q(contract_type__labor_regime__code='LOSEP')),
            count_ct=Count('id', filter=Q(contract_type__labor_regime__code='CT'))
        )
        context['total_active'] = aggs.get('total_active', 0)
        context['count_losep'] = aggs.get('count_losep', 0)
        context['count_ct'] = aggs.get('count_ct', 0)

        context['regimes'] = LaborRegime.objects.filter(is_active=True).prefetch_related('contract_types')
        context['schedules'] = Schedule.objects.filter(is_active=True)
        context['units'] = AdministrativeUnit.objects.filter(is_active=True)

        return context


class ValidateEmployeeAPIView(LoginRequiredMixin, View):
    def get(self, request, doc_number):
        try:
            # 1. Buscar la persona activa
            person = Person.objects.filter(document_number=doc_number, is_active=True).first()
            if not person:
                return JsonResponse({
                    'success': False,
                    'message': 'Cédula no registrada o persona inactiva.'
                })

            # 2. Si existe un empleado activo relacionado, bloquear (no debe ser empleado activo)
            active_employee = Employee.objects.filter(person=person, is_active=True).first()
            if active_employee:
                return JsonResponse({
                    'success': False,
                    'message': 'Atención: la persona ya es un empleado activo.'
                })

            # 3. Buscar un registro de Employee vinculado que tenga una partida presupuestaria asignada
            employees = Employee.objects.filter(person=person).select_related('person').prefetch_related('current_budget_line__position_item')
            employee_with_line = None
            budget_line = None
            for emp in employees:
                bl = emp.current_budget_line.first()
                if bl:
                    employee_with_line = emp
                    budget_line = bl
                    break

            if not employee_with_line or not budget_line:
                return JsonResponse({
                    'success': False,
                    'message': 'Bloqueo: La persona no tiene una partida presupuestaria asignada. Asigne una partida antes de continuar.'
                })

            # 4. Verificar si ya tiene contrato formal activo
            has_active = ManagementPeriod.objects.filter(
                employee=employee_with_line, status__code='ACTIVO'
            ).exists()

            if has_active:
                return JsonResponse({
                    'success': False,
                    'message': 'Atención: La persona ya posee un Inicio de Gestión (Contrato) vigente.'
                })

            return JsonResponse({
                'success': True,
                'employee': {
                    'id': employee_with_line.id,
                    'full_name': person.full_name,
                    'photo': person.photo.url if person.photo else None,
                    'budget_line': {
                        'id': budget_line.id,
                        'number': budget_line.number_individual or budget_line.code,
                        'position': budget_line.position_item.name if budget_line.position_item else 'SIN CARGO'
                    }
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class GetAvailableBudgetLinesAPIView(LoginRequiredMixin, View):
    def get(self, request, unit_id):
        # Buscamos partidas que estén LIBRES para esa unidad
        from budget.models import BudgetLine

        # Ajusta este filtro según cómo vinculaste la Unidad con la Partida
        lines = BudgetLine.objects.filter(
            # Ejemplo: Si la partida tiene relación con la unidad o vía actividad
            status_item__code='LIBRE',
            is_active=True
        ).select_related('position_item')

        data = [{
            'id': l.id,
            'number_individual': l.number_individual or l.code,
            'position_name': l.position_item.name if l.position_item else 'SIN CARGO',
            'remuneration': str(l.remuneration)
        } for l in lines]

        return JsonResponse({'success': True, 'lines': data})


class ManagementPeriodTablePartialView(LoginRequiredMixin, View):
    def get(self, request):
        # 1. Filtros
        q = request.GET.get('q', '').strip()
        regime_code_filter = request.GET.get('regime_code', '').strip()
        unit_id = request.GET.get('unit', '')
        status_code = request.GET.get('status_code', '')

        # 2. QuerySet REALMENTE Optimizado
        queryset = ManagementPeriod.objects.select_related(
            'employee__person',
            'budget_line__position_item',
            'contract_type__labor_regime',
            'administrative_unit',
            'status'
        ).order_by('-start_date')

        # 3. Filtros (Igual que antes pero sin evaluar el queryset todavía)
        if q:
            queryset = queryset.filter(
                Q(employee__person__first_name__icontains=q) |
                Q(employee__person__last_name__icontains=q) |
                Q(employee__person__document_number__icontains=q) |
                Q(document_number__icontains=q)
            )
        if regime_code_filter:
            queryset = queryset.filter(contract_type__labor_regime__code=regime_code_filter)
        if unit_id:
            queryset = queryset.filter(administrative_unit_id=unit_id)
        if status_code:
            queryset = queryset.filter(status__code=status_code)

        # 4. Paginación de Servidor (Aquí es donde ocurre la magia)
        from django.core.paginator import Paginator, EmptyPage
        page = int(request.GET.get('page', 1))
        page_size = 10  # Mostrar 10 registros por página (consistente con otras tablas)

        paginator = Paginator(queryset, page_size)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(1)

        # 5. Renderizado (Solo procesará 50 filas, no 6450)
        html = render_to_string(
            'contract/partials/partial_management_period_table.html',
            {'periods': page_obj},
            request=request
        )

        # 6. Estadísticas Dinámicas para las tarjetas superiores
        regimes_stats = LaborRegime.objects.filter(is_active=True).annotate(
            count=Count('contract_types__management_periods',
                        filter=Q(contract_types__management_periods__is_active=True))
        ).values('code', 'name', 'count')
        total_active = ManagementPeriod.objects.filter(is_active=True).count()

        return JsonResponse({
            'success': True,
            'table_html': html,
            'stats': {
                'total': total_active,
                'regimes': list(regimes_stats)
            },
            'pagination': {
                'total': paginator.count,
                'page': page_obj.number,
                'has_next': page_obj.has_next(),
                'has_prev': page_obj.has_previous(),
                'start': page_obj.start_index(),
                'end': page_obj.end_index(),
            }
        })


class ManagementPeriodTerminateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Finaliza un contrato y libera automáticamente la partida presupuestaria.
    """
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        reason = request.POST.get('reason', '').strip()

        if not reason:
            return JsonResponse({'success': False, 'message': 'El motivo de salida es obligatorio.'}, status=400)

        try:
            with transaction.atomic():
                # 1. Obtener estados
                finalizado_status = CatalogItem.objects.get(catalog__code='STATUS_CONTRACT', code='FINALIZADO')
                libre_status = CatalogItem.objects.get(catalog__code='BUDGET_STATUS', code='LIBRE')
                current_status = period.employee.employment_status.code
                exit_status = 'PERSONA'
                # 2. Finalizar el Periodo
                period.status = finalizado_status
                if not period.end_date:
                    period.end_date = timezone.now().date()
                period.updated_by = request.user
                period.save()
                mapping = {
                    'EMPLEADO': 'EX_EMPLEADO',
                    'TRABAJADOR': 'EX_TRABAJADOR',
                    'CONTRATADO': 'EX_EMPLEADO',
                    'PROFESIONAL': 'EX_PROFESIONAL'
                }
                exit_status = mapping.get(current_status, 'PERSONA')
                period.employee.set_status(exit_status)

                # Cambiar is_active del empleado a False
                period.employee.is_active = False
                period.employee.save()

                # 3. Liberar la Partida
                budget_line = period.budget_line
                budget_line.status_item = libre_status
                budget_line.current_employee = None
                budget_line.updated_by = request.user
                budget_line.save()

                # --- 4. REGISTRO EN HISTORIAL DE CONTRATO ---
                History.objects.create(
                    employee=period.employee,
                    contract=period,
                    user_register=request.user.get_full_name() or request.user.username,
                    type='TERMINACIÓN',
                    reason=reason  # Aquí se guarda lo que el usuario escribió en el modal
                )

                # 5. Auditoría en Historial de Partida (Ya lo tenías)
                BudgetModificationHistory.objects.create(
                    budget_line=budget_line,
                    modified_by=request.user,
                    modification_type='RELEASE',
                    field_name='Estado y Ocupante',
                    old_value=f"Ocupada por {period.employee.person.full_name}",
                    new_value="LIBRE / VACANTE",
                    reason=f"Terminación de contrato. Motivo: {reason}"
                )

            return JsonResponse({
                'success': True,
                'message': 'Gestión finalizada, partida liberada y registro guardado en el historial.'
            })

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Error técnico: {str(e)}'}, status=500)


class ManagementPeriodCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'contract.add_managementperiod'

    def post(self, request):
        data = request.POST
        try:
            with transaction.atomic():
                status_initial = CatalogItem.objects.get(
                    catalog__code='STATUS_CONTRACT', code='SIN_FIRMAR'
                )

                employee = get_object_or_404(Employee, pk=data.get('employee'))
                budget_line = employee.current_budget_line.first()

                # Creamos la instancia SIN document_number (el save() lo pondrá)
                period = ManagementPeriod(
                    employee=employee,
                    budget_line=budget_line,
                    contract_type_id=data.get('contract_type'),
                    administrative_unit_id=data.get('administrative_unit'),
                    schedule_id=data.get('schedule'),
                    status=status_initial,

                    # Estos campos se mantienen manuales
                    institutional_need_memo=data.get('institutional_need_memo', '').strip().upper(),
                    budget_certification=data.get('budget_certification', '').strip().upper(),
                    workplace=data.get('workplace', '').strip().upper(),
                    job_functions=data.get('job_functions', '').strip(),
                    start_date=data.get('start_date'),
                    end_date=data.get('end_date') if data.get('end_date') else None,
                    created_by=request.user
                )

                period.full_clean()
                period.save()  # Aquí se dispara la secuencia y el update del Employee

                # Si se solicitó marcar como jefe inmediato, actualizar employee.is_boss y unit.boss
                try:
                    is_boss_flag = data.get('is_boss')
                    is_boss = str(is_boss_flag).lower() in ('1', 'true', 'on', 'yes')
                    if is_boss:
                        try:
                            employee.is_boss = True
                            employee.save(update_fields=['is_boss'])
                        except Exception as e:
                            print(f"No se pudo marcar employee.is_boss=True: {e}")

                        try:
                            unit = AdministrativeUnit.objects.filter(pk=period.administrative_unit_id).first()
                            if unit:
                                unit.boss = employee
                                unit.save(update_fields=['boss'])
                        except Exception as e:
                            print(f"No se pudo actualizar AdministrativeUnit.boss: {e}")
                except Exception:
                    pass

                return JsonResponse({
                    'success': True,
                    'message': f'Gestión {period.document_number} registrada y área del empleado actualizada.'
                })

        except ValidationError as e:
            # Esto le dirá EXACTAMENTE qué campo falla en la consola de PyCharm
            return JsonResponse({'success': False, 'errors': e.message_dict}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ManagementPeriodSignView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Acción para legalizar/firmar el contrato."""
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        try:
            with transaction.atomic():
                status_signed = CatalogItem.objects.get(
                    catalog__code='STATUS_CONTRACT',
                    code='FIRMADO'
                )
                period.status = status_signed
                period.updated_by = request.user
                period.save()
                regime = period.contract_type.labor_regime.code  # LOSEP, CT, etc.
                ctype = period.contract_type.code
                new_status = 'EMPLEADO'
                if regime == 'CT':
                    new_status = 'TRABAJADOR'
                elif regime == 'LOSEP':
                    if 'OCASIONAL' in ctype:
                        new_status = 'CONTRATADO'
                    elif 'PROFESIONAL' in ctype:
                        new_status = 'PROFESIONAL'
                    else:
                        new_status = 'EMPLEADO'
                period.employee.set_status(new_status)

                # --- REGISTRO EN HISTORIAL DE CONTRATO ---
                History.objects.create(
                    employee=period.employee,
                    contract=period,
                    user_register=request.user.get_full_name() or request.user.username,
                    type='FIRMA',
                    reason='CONTRATO FIRMADO'
                )

                # --- REGISTRO EN HISTORIAL DE HORARIOS ---
                from schedule.models import EmployeeScheduleHistory
                EmployeeScheduleHistory.objects.create(
                    employee=period.employee,
                    schedule=period.schedule,
                    start_date=period.start_date,
                    end_date=period.end_date,
                    reason='Asignación de Horario',
                    is_current=True,
                    created_by=request.user
                )

            return JsonResponse({
                'success': True,
                'message': 'El contrato ha sido legalizado y registrado en el historial.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ManagementPeriodDetailAPIView(LoginRequiredMixin, View):
    """Retorna el JSON con todos los datos para el Expediente y el formulario de edición"""

    def get(self, request, pk):
        p = get_object_or_404(ManagementPeriod, pk=pk)
        return JsonResponse({
            'success': True,
            'period': {
                'id': p.id,
                'signed_document_url': p.signed_document.url if p.signed_document else None,
                'document_number': p.document_number,
                'employee_name': p.employee.person.full_name,
                'employee_photo': p.employee.person.photo.url if p.employee.person.photo else None,
                'status_name': p.status.name,
                'status_code': p.status.code,
                'budget_line_number': p.budget_line.number_individual or p.budget_line.code,
                'position_name': p.budget_line.position_item.name,
                'unit_name': p.administrative_unit.name,
                'institutional_need_memo': p.institutional_need_memo,
                'budget_certification': p.budget_certification,
                'start_date': p.start_date.isoformat(),  # Formato YYYY-MM-DD para el input date
                'start_date_formatted': p.start_date.strftime('%d/%m/%Y'),
                'end_date': p.end_date.isoformat() if p.end_date else '',
                'end_date_formatted': p.end_date.strftime('%d/%m/%Y') if p.end_date else 'INDEFINIDO',
                'schedule_id': p.schedule.id,
                'schedule_name': p.schedule.name,
                'workplace': p.workplace,
                'contract_type_name': p.contract_type.name,
                'job_functions': p.job_functions,
            }
        })


class ManagementPeriodPartialUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Procesa la actualización de campos específicos desde el SweetAlert del Expediente"""
    permission_required = 'contract.change_managementperiod'

    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        if period.status.code != 'SIN_FIRMAR':
            return JsonResponse({
                'success': False,
                'message': 'Error de Integridad: No es posible editar un contrato ya firmado o finalizado.'
            }, status=403)
        data = request.POST
        try:
            with transaction.atomic():
                # Actualización de campos permitidos
                period.document_number = data.get('doc', '').strip().upper()
                period.workplace = data.get('workplace', '').strip().upper()
                period.institutional_need_memo = data.get('memo', '').strip().upper()
                period.budget_certification = data.get('cert', '').strip().upper()
                period.start_date = data.get('start')
                period.end_date = data.get('end') if data.get('end') else None
                period.schedule_id = data.get('schedule')
                period.job_functions = data.get('functions', '').strip()

                period.updated_by = request.user
                period.full_clean()
                period.save()

                return JsonResponse({'success': True, 'message': 'Expediente actualizado correctamente.'})
        except ValidationError as e:
            return JsonResponse({'success': False, 'message': 'Error de validación: ' + str(e.message_dict)},
                                status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ManagementPeriodUploadDocView(LoginRequiredMixin, View):
    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        file = request.FILES.get('contract_file')

        if not file:
            return JsonResponse({'success': False, 'message': 'No se seleccionó ningún archivo.'}, status=400)

        # 1. Validaciones de Seguridad
        if not file.name.lower().endswith('.pdf'):
            return JsonResponse({'success': False, 'message': 'Solo se permiten archivos PDF.'}, status=400)

        if file.size > 2 * 1024 * 1024:  # 2MB
            return JsonResponse({'success': False, 'message': 'El archivo excede el límite de 2MB.'}, status=400)

        try:
            # 2. Guardar archivo (Django maneja la ruta vía upload_to definido en el modelo)
            # Si ya existe uno, eliminamos el anterior para no dejar basura en el server
            if period.signed_document:
                if os.path.isfile(period.signed_document.path):
                    os.remove(period.signed_document.path)

            period.signed_document = file
            period.updated_by = request.user
            period.save()

            return JsonResponse({
                'success': True,
                'message': 'Documento legalizado cargado correctamente.',
                'file_url': period.signed_document.url
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


class ManagementPeriodDeleteDocView(LoginRequiredMixin, View):
    def post(self, request, pk):
        period = get_object_or_404(ManagementPeriod, pk=pk)
        try:
            if period.signed_document:
                # Eliminación física
                if os.path.isfile(period.signed_document.path):
                    os.remove(period.signed_document.path)

                period.signed_document = None
                period.save()
                return JsonResponse({'success': True, 'message': 'Documento eliminado del expediente.'})
            return JsonResponse({'success': False, 'message': 'No hay documento para eliminar.'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)
