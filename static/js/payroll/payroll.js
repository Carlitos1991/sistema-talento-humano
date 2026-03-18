// ==========================================
// MODAL GENÉRICO PARA TODO EL SISTEMA
// ==========================================
// Wrapper de SweetAlert para asegurar que los diálogos de tipo
// success/info/error muestren solo el botón `OK` (elimina botones Cancel si aparecen).
try {
    if (typeof Swal !== 'undefined' && typeof Swal.fire === 'function') {
        const _origSwalFire = Swal.fire.bind(Swal);
        Swal.fire = function (...args) {
            // Detectar icon si se pasa como objeto o como 3er argumento (title,text,icon)
            let icon = null;
            if (args.length === 1 && typeof args[0] === 'object') {
                icon = args[0].icon;
            } else if (args.length >= 3) {
                icon = args[2];
            }
            const result = _origSwalFire(...args);
            // Si el diálogo es de resultado (success/info/error), eliminar cualquier boton Cancel que pudiera persistir
            if (icon && ['success', 'info', 'error'].includes(String(icon))) {
                setTimeout(() => {
                    try {
                        document.querySelectorAll('.swal2-container .swal2-cancel').forEach(el => el.remove());
                    } catch (e) { /* ignore */
                    }
                }, 40);
            }
            return result;
        };
    }
} catch (e) { /* ignore */
}

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

                // Mostrar mensaje: advertencia si hay feriados, info si no los hay
                if (data.warning) {
                    Swal.fire({
                        title: 'Advertencia',
                        text: data.warning,
                        icon: 'warning',
                        confirmButtonText: 'Entendido',
                        showCloseButton: true,
                        allowOutsideClick: false
                    });
                } else if (data.info) {
                    Swal.fire({
                        title: 'Información',
                        text: data.info,
                        icon: 'info',
                        confirmButtonText: 'Entendido',
                        showCloseButton: true,
                        allowOutsideClick: false
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
    yearInput.addEventListener('input', function (e) {
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
                window.openGenerateModal(id, name, true);
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

    // Cerrar cualquier modal subyacente inmediatamente
    if (typeof window.closeGenerateModal === 'function') {
        window.closeGenerateModal();
    }
    try {
        const mg = document.getElementById('modalGeneratePayroll');
        if (mg) {
            mg.classList.remove('is-active');
            mg.style.display = 'none';
            document.body.classList.remove('modal-open');
        }
    } catch (e) {
    }

    // Usar AbortController para permitir cancelar la petición al pulsar "Cancelar"
    const controller = new AbortController();
    const signal = controller.signal;

    const html = `<div style="display:flex;align-items:center;gap:12px;">
                    <div style="width:36px;height:36px;border:4px solid #e6e6e6;border-top-color:#4e73df;border-radius:50%;animation:sw-spin 1s linear infinite;"></div>
                    <div style="font-size:16px;font-weight:600;">Calculando, Por favor espere</div>
                  </div>`;

    // Mostrar SweetAlert con solo botón Cancelar centrado
    Swal.fire({
        title: '',
        html: html,
        showConfirmButton: false,
        showCancelButton: true,
        cancelButtonText: 'Cancelar',
        allowOutsideClick: false,
        scrollbarPadding: false, // <--- SOLUCIÓN AL PARPADEO (1/2): Evita que la tabla salte
        customClass: {popup: 'swal2-recalc-popup'},
        didOpen: () => {
            try {
                // Inyectar estilos rápidos para centrar y keyframes si no existen
                const styleId = 'swal2-recalc-style';
                if (!document.getElementById(styleId)) {
                    const style = document.createElement('style');
                    style.id = styleId;
                    style.innerHTML = `.swal2-recalc-popup .swal2-actions{justify-content:center!important;} .swal2-recalc-popup .swal2-html-container{overflow:visible!important;max-height:none!important;} @keyframes sw-spin{to{transform:rotate(360deg)}}`;
                    document.head.appendChild(style);
                }
                // Ocultar temporalmente cualquier confirm que pudiera permanecer
                const conf = document.querySelector('.swal2-confirm');
                if (conf) conf.style.display = 'none';
                // Forzar que el contenido no tenga scroll
                const htmlCont = document.querySelector('.swal2-html-container');
                if (htmlCont) {
                    htmlCont.style.overflow = 'visible';
                    htmlCont.style.maxHeight = 'none';
                }
                const content = document.querySelector('.swal2-content');
                if (content) {
                    content.style.overflow = 'visible';
                    content.style.maxHeight = 'none';
                }
                // Vincular botón cancelar al AbortController
                const btn = document.querySelector('.swal2-cancel');
                if (btn) {
                    btn.addEventListener('click', function () {
                        try {
                            controller.abort();
                        } catch (e) {
                        }
                    });
                    btn.style.minWidth = '120px';
                }
                // Por seguridad: si el confirm sigue presente, eliminarlo
                setTimeout(() => {
                    try {
                        const containers = document.querySelectorAll('.swal2-container');
                        containers.forEach(c => {
                            if (c.innerText && c.innerText.indexOf('Calculando, Por favor espere') !== -1) {
                                const conf = c.querySelector('.swal2-confirm');
                                if (conf) conf.remove();
                                const canc = c.querySelector('.swal2-cancel');
                                if (canc) canc.style.marginLeft = '0';
                            }
                        });
                    } catch (e) {
                    }
                }, 60);
            } catch (e) {
            }
        }
    });

    fetch(url, {
        method: 'POST',
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()},
        body: new URLSearchParams({'period_id': id}),
        signal: signal
    }).then(r => r.json()).then(data => {
        try {
            Swal.close();
        } catch (e) {
        }
        // Esperar un poco para asegurar cierre completo del DOM anterior
        setTimeout(() => {
            try {
                document.querySelectorAll('.swal2-container').forEach(c => c.remove());
            } catch (e) {
            }
            try {
                document.querySelectorAll('.swal2-cancel').forEach(el => el.remove());
            } catch (e) {
            }
            try {
                document.querySelectorAll('.swal2-confirm').forEach(el => el.remove());
            } catch (e) {
            }

            if (data.status === 'success' || data.success || data.message) {
                Swal.fire({
                    title: 'Éxito',
                    text: data.message || 'Operación completada',
                    icon: 'success',
                    confirmButtonText: 'OK',
                    showCancelButton: false,
                    scrollbarPadding: false // <--- SOLUCIÓN AL PARPADEO (2/2)
                }).then(() => {
                    // <--- RECARGA INTELIGENTE (Sin pantallazo blanco de recarga de página)
                    if (typeof window.loadTable === 'function') {
                        window.loadTable(id); // Recarga tabla en Gestión de Roles
                    } else if (typeof window.loadTablePage === 'function') {
                        window.loadTablePage(1); // Recarga tabla en Periodos
                    } else {
                        location.reload(); // Fallback por si acaso
                    }
                });
            } else if (data.status === 'info') {
                Swal.fire({
                    title: 'Info',
                    text: data.message,
                    icon: 'info',
                    confirmButtonText: 'OK',
                    showCancelButton: false,
                    scrollbarPadding: false
                });
            } else {
                Swal.fire({
                    title: 'Error',
                    text: data.message || 'Error al generar',
                    icon: 'error',
                    confirmButtonText: 'OK',
                    showCancelButton: false,
                    scrollbarPadding: false
                });
            }
        }, 140);
    }).catch(err => {
        try {
            Swal.close();
        } catch (e) {
        }
        if (err && err.name === 'AbortError') return;
        console.error(err);
        setTimeout(() => {
            Swal.fire({
                title: 'Error',
                text: 'Fallo de comunicación',
                icon: 'error',
                confirmButtonText: 'OK',
                showCancelButton: false,
                scrollbarPadding: false
            });
        }, 140);
    });
}

function downloadReport(kind) {
    const id = _resolveCurrentPeriodId();
    if (!id) return Swal.fire('Error', 'Periodo no seleccionado', 'error');

    let url = '';
    if (kind === 'banco') {
        url = window.URLS.reporteBanco;
    } else if (kind === 'nomina') {
        url = window.URLS.reporteNomina;
    } else if (kind === 'negativos') {
        url = window.URLS.reporteNegativos;
    }

    if (!url) return Swal.fire('Error', 'URL de reporte no encontrada', 'error');

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
            Swal.fire('Hecho', data.message, 'success').then(() => location.reload());
        } else {
            Swal.fire('Error', data.message || 'No se pudo sellar', 'error');
        }
    }).catch(err => {
        console.error(err);
        Swal.fire('Error', 'Fallo de comunicación', 'error');
    });
}