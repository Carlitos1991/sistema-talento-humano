// ==========================================
// MODAL GENÉRICO PARA TODO EL SISTEMA
// ==========================================
function openPayrollModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');

            // Inicializar Select2 dinámicamente si el modal lo requiere
            const modalOverlay = document.querySelector('.modal-overlay');
            if (modalOverlay) {
                $(modalOverlay).find('select').select2({
                    width: '100%',
                    dropdownParent: $(modalOverlay)
                });
                $(modalOverlay).find('input[type="text"]').addClass('input-field');
            }

            // Inicializar el código del modal de período si existe
            initializePeriodModal();
        })
        .catch(error => console.error('Error cargando el modal:', error));
}

function initializePeriodModal() {
    const monthSelect = document.querySelector('select[name="month"]');
    const yearInput = document.querySelector('input[name="year"]');
    const startDateInput = document.querySelector('input[name="start_date"]');
    const endDateInput = document.querySelector('input[name="end_date"]');
    const workingDaysInput = document.querySelector('input[name="working_days"]');
    const submitBtn = document.querySelector('button[type="submit"]');

    if (!monthSelect || !yearInput) {
        return; // No es un modal de período
    }

    let isCalculating = false;
    
    // Detectar si es modo edición (si hay valores preexistentes de fecha)
    const isEditMode = startDateInput.value && endDateInput.value;

    // Cargar año actual por defecto si está vacío
    if (!yearInput.value) {
        const currentYear = new Date().getFullYear().toString();
        yearInput.value = currentYear;
    }

    // Establecer mes actual por defecto si está vacío
    if (!monthSelect.value) {
        const months = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 
                        'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE'];
        const currentMonth = months[new Date().getMonth()];
        monthSelect.value = currentMonth;
        
        // Reinicializar Select2 para que refleje el nuevo valor
        $(monthSelect).val(currentMonth).trigger('change');
    }

    // Función para calcular fechas y días laborables
    async function calculateWorkingDays() {
        const month = monthSelect.value;
        const year = yearInput.value;

        if (!month || !year || year.length !== 4) {
            startDateInput.value = '';
            endDateInput.value = '';
            workingDaysInput.value = '';
            if (submitBtn) submitBtn.disabled = true;
            return;
        }

        isCalculating = true;
        if (submitBtn) submitBtn.disabled = true;

        try {
            const calculateUrl = '/payroll/api/calculate-working-days/?month=' + encodeURIComponent(month) + '&year=' + encodeURIComponent(year);
            const response = await fetch(calculateUrl);
            
            if (!response.ok) {
                throw new Error('API retornó estado: ' + response.status);
            }
            
            const data = await response.json();

            if (data.status === 'success') {
                startDateInput.value = data.start_date;
                endDateInput.value = data.end_date;
                workingDaysInput.value = data.working_days;
                
                if (submitBtn) submitBtn.disabled = false;
                
                // Mostrar advertencia si hay (DESPUÉS de calcular)
                if (data.warning) {
                    Swal.fire({
                        title: 'Advertencia',
                        text: data.warning,
                        icon: 'warning',
                        confirmButtonText: 'Entendido'
                    });
                }
            } else {
                Swal.fire('Error', 'No se pudieron calcular los días laborables: ' + data.message, 'error');
                if (submitBtn) submitBtn.disabled = true;
                // Limpiar campos en caso de error
                startDateInput.value = '';
                endDateInput.value = '';
                workingDaysInput.value = '';
            }
        } catch (error) {
            Swal.fire('Error', 'Error al conectar con el servidor: ' + error.message, 'error');
            if (submitBtn) submitBtn.disabled = true;
            // Limpiar campos en caso de error
            startDateInput.value = '';
            endDateInput.value = '';
            workingDaysInput.value = '';
        } finally {
            isCalculating = false;
        }
    }

    // Escuchar cambios en mes y año
    // Para Select2, usar el evento 'change.select2' en lugar de 'change'
    $(monthSelect).on('change.select2', calculateWorkingDays);
    yearInput.addEventListener('change', calculateWorkingDays);
    
    // Validar que el año solo acepte números y máximo 4 caracteres
    yearInput.addEventListener('input', function(e) {
        const oldValue = this.value;
        this.value = this.value.replace(/[^0-9]/g, '').slice(0, 4);
        // Solo llamar a calculateWorkingDays si el valor cambió y tenemos 4 dígitos
        if (oldValue !== this.value && this.value.length === 4) {
            calculateWorkingDays();
        }
    });

    // En modo edición, calcular automáticamente para mostrar cambios por nuevos feriados
    // En modo creación, también calcular después de establecer valores por defecto
    setTimeout(() => {
        calculateWorkingDays();
    }, 100);
}

function closePayrollModal() {
    document.getElementById('modal-root').innerHTML = '';
    document.body.classList.remove('modal-open');
}

function submitPayrollForm(event) {
    event.preventDefault();
    const form = event.target;

    // Validar que los campos calculados tengan valores
    const startDate = form.querySelector('input[name="start_date"]')?.value;
    const endDate = form.querySelector('input[name="end_date"]')?.value;
    const workingDays = form.querySelector('input[name="working_days"]')?.value;
    const month = form.querySelector('select[name="month"]')?.value;
    const year = form.querySelector('input[name="year"]')?.value;

    if (!month || !year) {
        Swal.fire('Error', 'Debe seleccionar un mes y un año', 'error');
        return;
    }

    if (!startDate || !endDate || !workingDays) {
        Swal.fire('Error', 'Los campos de fecha y días laborables no se calcularon correctamente. Por favor aguarde un momento e intente nuevamente.', 'error');
        return;
    }

    const formData = new FormData(form);

    // Obtener CSRF token del formulario
    const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]')?.value || 
                      document.querySelector('[name="csrfmiddlewaretoken"]')?.value;

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken
        }
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                closePayrollModal();
                Swal.fire({
                    icon: 'success',
                    title: '¡Guardado!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                })
                    .then(() => location.reload());
            } else {
                let errorMsg = data.message;
                if (data.errors) {
                    // Si errors es un objeto, extraer el primer mensaje
                    if (typeof data.errors === 'object') {
                        const firstKey = Object.keys(data.errors)[0];
                        if (Array.isArray(data.errors[firstKey])) {
                            errorMsg = data.errors[firstKey][0];
                        }
                    } else {
                        errorMsg = data.errors;
                    }
                }
                Swal.fire('Error', errorMsg, 'error');
            }
        })
        .catch(error => Swal.fire('Error', 'Ocurrió un problema de comunicación: ' + error.message, 'error'));
}

// 1. Abrir Modal
function openContributionModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            // Inyectamos el HTML
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');

            // ==========================================
            // A. INICIALIZAR SELECT2 CON JQUERY
            // ==========================================
            $('#contributionForm select').select2({
                width: '100%',
                // El dropdownParent evita que el buscador de Select2 se esconda detrás del modal
                dropdownParent: $('#contributionModalOverlay')
            });

            // Forzar la clase de tu diseño a los inputs nativos
            $('#contributionForm input[type="text"]').addClass('input-field');

            // ==========================================
            // B. LÓGICA DE ACORDEÓN (ANIMACIÓN SUAVE)
            // ==========================================
            const $mappingCheckbox = $('#contributionForm input[name="has_mapping"]');
            const $budgetFieldsBox = $('#budgetMappingFields');

            $mappingCheckbox.on('change', function () {
                if ($(this).is(':checked')) {
                    // Se desliza hacia abajo (abre)
                    $budgetFieldsBox.slideDown(300);
                } else {
                    // Se desliza hacia arriba (cierra)
                    $budgetFieldsBox.slideUp(300);
                }
            });
        })
        .catch(error => console.error('Error cargando el modal:', error));
}

// 2. Cerrar Modal
function closeContributionModal() {
    document.getElementById('modal-root').innerHTML = '';
    document.body.classList.remove('modal-open');
}

// 3. Enviar Formulario por AJAX
function submitContributionForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                closeContributionModal();
                Swal.fire({
                    icon: 'success',
                    title: '¡Excelente!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                }).then(() => {
                    location.reload();
                });
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un problema de comunicación con el servidor.', 'error');
        });
}

// 4. Cargar tabla parcial sin recargar la página (AJAX)
function toggleInactiveContributions(showInactive) {
    // Hacemos la petición silenciosa a la vista
    fetch(`?show_inactive=${showInactive}`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(response => response.text())
        .then(html => {
            // Reemplazamos el cuerpo de la tabla con las nuevas filas
            const tbody = document.querySelector('.managed-table tbody');
            tbody.innerHTML = html;

            // Reiniciamos el paginador y buscador (table-manager.js)
            // para que cuente las nuevas filas renderizadas
            const table = document.querySelector('.managed-table');
                if (table && table._tableManager) {
                    table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                    table._tableManager.currentRows = [...table._tableManager.originalRows];
                    if (typeof table._tableManager.render === 'function') {
                        table._tableManager.render();
                    }
                }
        })
        .catch(error => console.error('Error cargando la tabla:', error));
}

// ---------- INCOME: modal + submit + toggle ----------
function openIncomeModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');

            // Inicializar select2 si hay selects
            $('#incomeForm select').select2({width: '100%', dropdownParent: $('#incomeModalOverlay')});
            $('#incomeForm input[type="text"]').addClass('input-field');

            // Lógica de acordeón para mapeo presupuestario
            const $incMappingCheckbox = $('#incomeForm input[name="has_mapping"]');
            const $incBudgetBox = $('#budgetMappingFields');
            $incMappingCheckbox.on('change', function () {
                if ($(this).is(':checked')) {
                    $incBudgetBox.slideDown(300);
                } else {
                    $incBudgetBox.slideUp(300);
                }
            });
        })
        .catch(error => console.error('Error cargando el modal de ingreso:', error));
}

function submitIncomeForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                closeContributionModal();
                Swal.fire({
                    icon: 'success',
                    title: '¡Excelente!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                })
                    .then(() => location.reload());
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un problema con el servidor.', 'error');
        });
}

function toggleInactiveIncomes(showInactive) {
    fetch(`?show_inactive=${showInactive}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            const tbody = document.querySelector('.managed-table tbody');
            tbody.innerHTML = html;
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.render === 'function') table._tableManager.render();
            }
        })
        .catch(error => console.error('Error cargando la tabla de ingresos:', error));
}

// ---------- DEDUCTION: modal + submit + toggle ----------
function openDeductionModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');
            $('#deductionForm select').select2({width: '100%', dropdownParent: $('#deductionModalOverlay')});
            $('#deductionForm input[type="text"]').addClass('input-field');

            // Lógica de acordeón para mapeo presupuestario
            const $dedMappingCheckbox = $('#deductionForm input[name="has_mapping"]');
            const $dedBudgetBox = $('#budgetMappingFields');
            $dedMappingCheckbox.on('change', function () {
                if ($(this).is(':checked')) {
                    $dedBudgetBox.slideDown(300);
                } else {
                    $dedBudgetBox.slideUp(300);
                }
            });
        })
        .catch(error => console.error('Error cargando el modal de descuento:', error));
}

function submitDeductionForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                closeContributionModal();
                Swal.fire({
                    icon: 'success',
                    title: '¡Excelente!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                })
                    .then(() => location.reload());
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un problema con el servidor.', 'error');
        });
}

function toggleInactiveDeductions(showInactive) {
    fetch(`?show_inactive=${showInactive}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            const tbody = document.querySelector('.managed-table tbody');
            tbody.innerHTML = html;
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.render === 'function') table._tableManager.render();
            }
        })
        .catch(error => console.error('Error cargando la tabla de descuentos:', error));
}

// ---------- ACCOUNT: modal + submit ----------
function openAccountModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');

            // Inicializar select2 si existen selects dentro del modal
            $('#accountForm select').select2({width: '100%', dropdownParent: $('#accountModalOverlay')});
            $('#accountForm input[type="text"]').addClass('input-field');
        })
        .catch(error => console.error('Error cargando el modal de cuenta:', error));
}

function submitAccountForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                closeContributionModal();
                Swal.fire({icon: 'success', title: '¡Excelente!', text: data.message, timer: 1500, showConfirmButton: false})
                    .then(() => location.reload());
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un problema con el servidor.', 'error');
        });
}

function toggleInactiveAccounts(showInactive) {
    fetch(`?show_inactive=${showInactive}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            const tbody = document.querySelector('.managed-table tbody');
            tbody.innerHTML = html;
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.render === 'function') table._tableManager.render();
            }
        })
        .catch(error => console.error('Error cargando la tabla de cuentas:', error));
}

// Añadimos placeholders dinámicamente cuando se abre el modal de cuentas
const _origOpenAccountModal = window.openAccountModal;
function openAccountModal(url) {
    // reutiliza la función genérica si existe
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');
            // Set placeholders
            const $code = $('#accountForm input[name="code"]');
            const $name = $('#accountForm input[name="name"]');
            const $desc = $('#accountForm textarea[name="description"]');
            if ($code.length) $code.attr('placeholder', 'Ej: 1000');
            if ($name.length) $name.attr('placeholder', 'Ej: Caja');
            if ($desc.length) $desc.attr('placeholder', 'Descripción de la cuenta (opcional)');
            $('#accountForm select').select2({width: '100%', dropdownParent: $('#accountModalOverlay')});
            $('#accountForm input[type="text"]').addClass('input-field');
        })
        .catch(error => console.error('Error cargando el modal de cuenta:', error));
}

// Toggle: mostrar/ocultar periodos cerrados (AJAX)
function toggleInactivePeriods(showClosed) {
    fetch(`?show_closed=${showClosed}&json=1`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.json())
        .then(data => {
            const tbody = document.querySelector('.managed-table tbody');
            if (!tbody) return;

            // Reconstruimos filas desde JSON (evitamos inyectar HTML pre-renderizado del servidor)
            const rows = (data.periods || []).map(p => {
                const periodo = `${p.month} ${p.year}`;
                const dataSort = `${p.year}${String(p.month_num).padStart(2, '0')}`;

                let actions = '';
                if (!p.is_closed) {
                    actions += `<button type="button" class="btn-icon btn-views-action" title="Procesar / Recalcular" data-generate-id="${p.id}" data-generate-name="${periodo.replace(/'/g, "\\'")}"><i class="fas fa-cogs"></i></button>`;
                    if (p.novelty_url) {
                        actions += `<a href="${p.novelty_url}" class="btn-icon btn-success-action ms-2" title="Cargar Novedades al Periodo"><i class="fas fa-file-excel"></i></a>`;
                    }
                }
                if (p.payslip_url) {
                    actions += `<a href="${p.payslip_url}" class="btn-icon btn-search ms-2" title="Ver Roles Generados"><i class="fas fa-list"></i></a>`;
                }
                actions += `<button type="button" class="btn-icon btn-info-action ms-2" title="Generar Reportes" data-report-id="${p.id}" data-report-name="${periodo.replace(/'/g, "\\'")}" data-report-closed="${p.is_closed}"><i class="fas fa-university"></i></button>`;

                return `<tr>
                    <td class="fw-bold" data-sort="${dataSort}">${periodo}</td>
                    <td>${p.start_date} - ${p.end_date}</td>
                    <td class="text-center">${p.working_days}</td>
                    <td class="text-center">${p.is_closed ? '<span class="status-badge inactive"><i class="fas fa-times-circle"></i> Cerrado</span>' : '<span class="status-badge active"><i class="fas fa-check-circle"></i> Abierto</span>'}</td>
                    <td class="text-center actions"><div class="actions-wrapper">${actions}</div></td>
                </tr>`;
            }).join('');

            tbody.innerHTML = rows || `<tr><td colspan="5" class="text-center py-5 text-muted"><i class="fas fa-calendar-times fa-3x mb-3"></i><br>No hay periodos registrados.</td></tr>`;

            // Re-inicializar table-manager con las nuevas filas
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.render === 'function') table._tableManager.render();
            }
        })
        .catch(error => console.error('Error cargando periodos:', error));
}

// Fallback: asegurar que exista la función openGenerateModal
if (typeof window.openGenerateModal !== 'function') {
    window.openGenerateModal = function (id, name) {
        try {
            console.log('fallback openGenerateModal invoked', id, name);
            window.currentGenPeriodId = id;
            const modal = document.getElementById('modalGeneratePayroll');
            if (modal) {
                const nameEl = document.getElementById('gen-period-name');
                if (nameEl) nameEl.innerText = name;
                modal.style.display = 'flex';
                document.body.classList.add('modal-open');
            } else {
                console.warn('modalGeneratePayroll no encontrado en el DOM');
            }
        } catch (e) {
            console.error('Error fallback openGenerateModal:', e);
        }
    };
}

// Fallback para openReportModal
if (typeof window.openReportModal !== 'function') {
    window.openReportModal = function (id, name, isClosed) {
        try {
            console.log('fallback openReportModal invoked', id, name, isClosed);
            window.currentGenPeriodId = id;
            const modal = document.getElementById('modalReportOptions');
            if (modal) {
                const nameEl = document.getElementById('rep-period-name');
                if (nameEl) nameEl.innerText = name;
                const sellarBtn = document.getElementById('sellar-container');
                if (sellarBtn) sellarBtn.style.display = isClosed ? 'none' : 'block';
                modal.style.display = 'flex';
                document.body.classList.add('modal-open');
            } else {
                console.warn('modalReportOptions no encontrado en el DOM');
            }
        } catch (e) {
            console.error('Error fallback openReportModal:', e);
        }
    };
}

// Delegated event listener para botones generados dinámicamente
document.addEventListener('click', function (e) {
    try {
        console.debug('delegated click target:', e.target && e.target.tagName, e.target);
    } catch (ex) {
        // ignore
    }

    // compatibilidad: si closest no existe, hacer traversal manual
    function findAttr(node, attr) {
        let cur = node;
        while (cur && cur !== document) {
            if (cur.getAttribute && cur.getAttribute(attr) !== null) return cur;
            cur = cur.parentNode;
        }
        return null;
    }

    const genBtn = (e.target.closest && e.target.closest('[data-generate-id]')) || findAttr(e.target, 'data-generate-id');
    if (genBtn) {
        const id = genBtn.getAttribute('data-generate-id');
        const name = genBtn.getAttribute('data-generate-name') || '';
        console.log('delegated: generate click', id, name);
        try {
            if (typeof window.openGenerateModal === 'function') {
                window.openGenerateModal(id, name);
            } else {
                console.warn('openGenerateModal no definido');
            }
        } catch (err) {
            console.error('Error invoking openGenerateModal via delegation', err);
        }
        e.preventDefault();
        return;
    }

    const repBtn = (e.target.closest && e.target.closest('[data-report-id]')) || findAttr(e.target, 'data-report-id');
    if (repBtn) {
        const id = repBtn.getAttribute('data-report-id');
        const name = repBtn.getAttribute('data-report-name') || '';
        const isClosed = repBtn.getAttribute('data-report-closed') === 'true';
        console.log('delegated: report click', id, name, isClosed);
        try {
            if (typeof window.openReportModal === 'function') {
                window.openReportModal(id, name, isClosed);
            } else {
                console.warn('openReportModal no definido');
            }
        } catch (err) {
            console.error('Error invoking openReportModal via delegation', err);
        }
        e.preventDefault();
        return;
    }
});

// Actions relacionadas con los modales: generar, descargar reportes y sellar
function getCSRF() {
    return window.CSRF_TOKEN || (document.querySelector('input[name=csrfmiddlewaretoken]') && document.querySelector('input[name=csrfmiddlewaretoken]').value);
}

function _resolveCurrentPeriodId() {
    // La variable puede estar en window (fallback) o en el scope de modal_generate_payroll.js
    if (typeof window !== 'undefined' && typeof window.currentGenPeriodId !== 'undefined' && window.currentGenPeriodId) return window.currentGenPeriodId;
    if (typeof currentGenPeriodId !== 'undefined' && currentGenPeriodId) return currentGenPeriodId;
    return null;
}

function submitGenerate(mode) {
    const id = _resolveCurrentPeriodId();
    if (!id) return Swal.fire('Error', 'Periodo no seleccionado', 'error');
    const url = (mode === 'missing') ? window.URLS.generateMissing : window.URLS.generateAll;
    Swal.fire({title: 'Procesando...', didOpen: () => {Swal.showLoading();}});
    fetch(url, {
        method: 'POST',
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()},
        body: new URLSearchParams({'period_id': id})
    }).then(r => r.json()).then(data => {
        Swal.close();
        if (data.status === 'success' || data.success || data.message) {
            Swal.fire('Éxito', data.message || 'Operación completada', 'success').then(()=> location.reload());
        } else if (data.status === 'info') {
            Swal.fire('Info', data.message, 'info');
        } else {
            Swal.fire('Error', data.message || 'Error al generar', 'error');
        }
    }).catch(err=>{Swal.close(); console.error(err); Swal.fire('Error', 'Fallo de comunicación', 'error');});
}

function downloadReport(kind) {
    const id = _resolveCurrentPeriodId();
    if (!id) return Swal.fire('Error', 'Periodo no seleccionado', 'error');
    let url = (kind === 'banco') ? window.URLS.reporteBanco : window.URLS.reporteNomina;
    url = url.replace('999999', id);
    window.open(url, '_blank');
}

function sellarComoPagados() {
    const id = _resolveCurrentPeriodId();
    if (!id) return Swal.fire('Error', 'Periodo no seleccionado', 'error');
    const url = (window.URLS.periodMarkPaid || '').replace('999999', id);
    fetch(url, {method: 'POST', headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}})
        .then(r => r.json()).then(data => {
            if (data.success) {
                Swal.fire('Hecho', data.message, 'success').then(()=> location.reload());
            } else {
                Swal.fire('Error', data.message || 'No se pudo sellar', 'error');
            }
        }).catch(err=>{console.error(err); Swal.fire('Error', 'Fallo de comunicación', 'error');});
}