/**
 * PAYROLL.JS - GESTIÓN INTEGRAL DEL MÓDULO DE NÓMINA Y RRHH
 * Unificación de: Periodos, Generación, Modales, Roles (Payslips), Fondos de Reserva y Rubros.
 */

const PAYROLL_URLS = {
    recalculate: '/payroll/payslips/recalculate/',
    syncMissing: '/payroll/generate/missing/',
    seal: (id) => `/payroll/period/${id}/mark-paid/`,
    calculate: '/payroll/api/calculate-working-days/',
    tableList: '/payroll/periods/',
    status: '/payroll/payslips/recalculate-status/'
};

window.currentGenPeriodId = null;

async function safeJsonParse(response) {
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('text/html')) throw new Error('Error: El servidor devolvió HTML (Posible error 500).');
    const data = await response.json();
    if (!response.ok || (data.status === 'error' || data.success === false)) throw new Error(data.message || 'Error interno.');
    return data;
}

/* =================================================================================
   1. MODALES ESTÁTICOS DE NÓMINA (Generar y Sellar)
   ================================================================================= */
window.openGenerateModal = function (id, name, hasScopeChanges) {
    window.currentGenPeriodId = id;
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        const nameEl = document.getElementById('gen-period-name');
        if (nameEl) nameEl.innerText = name;
        const btnScope = document.getElementById('btn-generate-scope');
        if (btnScope) btnScope.style.display = (hasScopeChanges === 'true' || hasScopeChanges === true) ? 'flex' : 'none';
        modal.setAttribute('style', 'display: flex !important;');
        document.body.classList.add('modal-open');
    }
};

window.closeGenerateModal = function () {
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        modal.setAttribute('style', 'display: none !important;');
        document.body.classList.remove('modal-open');
        document.getElementById('generate-options').style.display = 'block';
        document.getElementById('generate-loading').style.display = 'none';
    }
};

window.openReportModal = function (id, name, isClosed) {
    window.currentGenPeriodId = id;
    const modal = document.getElementById('modalReportOptions');
    if (modal) {
        const nameEl = document.getElementById('rep-period-name');
        if (nameEl) nameEl.innerText = name;
        const sellarBtn = document.getElementById('sellar-container');
        if (sellarBtn) sellarBtn.style.display = (isClosed === 'true' || isClosed === true) ? 'none' : 'block';
        modal.setAttribute('style', 'display: flex !important;');
        document.body.classList.add('modal-open');
    }
};

window.closeReportModal = function () {
    const modal = document.getElementById('modalReportOptions');
    if (modal) {
        modal.setAttribute('style', 'display: none !important;');
        document.body.classList.remove('modal-open');
    }
};

/* =================================================================================
   2. MOTOR DE PROCESAMIENTO Y RECALCULO DE ROLES
   ================================================================================= */
window.submitGenerate = function (mode) {
    const periodId = window.currentGenPeriodId;
    if (!periodId) return;

    document.getElementById('generate-options').style.display = 'none';
    document.getElementById('generate-loading').style.display = 'block';

    const formData = new FormData();
    formData.append('period_id', periodId);
    let targetUrl = PAYROLL_URLS.recalculate;

    if (mode === 'missing') targetUrl = PAYROLL_URLS.syncMissing;
    else if (mode === 'scope') formData.append('scope', 'true');

    fetch(targetUrl, {
        method: 'POST', body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
    })
        .then(safeJsonParse)
        .then(data => {
            if (data.task_id) startGenerationPolling(data.task_id);
            else handleGenerationSuccess(data.message || 'Proceso completado.');
        })
        .catch(err => {
            window.closeGenerateModal();
            Swal.fire({icon: 'error', title: 'Error', text: err.message, scrollbarPadding: false, heightAuto: false});
        });
};

function startGenerationPolling(taskId) {
    Swal.fire({
        title: 'Calculando Nómina',
        html: `<div id="poll-msg">Iniciando proceso asíncrono...</div>`,
        allowOutsideClick: false, showConfirmButton: false, scrollbarPadding: false, heightAuto: false,
        didOpen: () => Swal.showLoading()
    });

    const poll = () => {
        fetch(`${PAYROLL_URLS.status}?task_id=${taskId}`)
            .then(safeJsonParse)
            .then(res => {
                if (res.done || res.status === 'SUCCESS' || res.success) {
                    handleGenerationSuccess(res.message || 'Nómina generada.');
                } else {
                    const msgEl = document.getElementById('poll-msg');
                    if (msgEl && res.progress) msgEl.innerText = `Progreso: ${res.progress}%`;
                    setTimeout(poll, 1000);
                }
            })
            .catch(err => Swal.fire('Error', err.message, 'error'));
    };
    poll();
}

function handleGenerationSuccess(message) {
    Swal.fire({
        icon: 'success', title: '¡Éxito!', text: message, timer: 2000,
        showConfirmButton: false, scrollbarPadding: false, heightAuto: false
    }).then(() => {
        window.closeGenerateModal();
        if (window.reloadTableData) window.reloadTableData(PAYROLL_URLS.tableList, '#period-table-container');
    });
}

window.sellarComoPagados = function () {
    const periodId = window.currentGenPeriodId;
    if (!periodId) return;

    Swal.fire({
        title: '¿Sellar periodo?',
        text: "Marcarás todos los roles como pagados y no podrás realizar más cambios.",
        icon: 'warning', showCancelButton: true, confirmButtonColor: '#10b981',
        confirmButtonText: 'Sí, sellar ahora', scrollbarPadding: false, heightAuto: false
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(PAYROLL_URLS.seal(periodId), {
                method: 'POST', headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
            })
                .then(safeJsonParse)
                .then(() => {
                    Swal.fire({
                        icon: 'success',
                        title: 'Periodo Cerrado',
                        scrollbarPadding: false,
                        heightAuto: false
                    }).then(() => {
                        window.closeReportModal();
                        if (window.reloadTableData) window.reloadTableData(PAYROLL_URLS.tableList, '#period-table-container');
                    });
                })
                .catch(err => Swal.fire('Error', err.message, 'error'));
        }
    });
};

/* =================================================================================
   3. INICIALIZADORES DE MODALES (Rubros y Periodos)
   ================================================================================= */

window.initializePeriodModal = function (root) {
    const monthSelect = root.querySelector('[name="month"]');
    const yearInput = root.querySelector('[name="year"]');
    const startDateInput = root.querySelector('[name="start_date"]');
    const endDateInput = root.querySelector('[name="end_date"]');
    const workingDaysInput = root.querySelector('[name="working_days"]');
    const submitBtn = root.querySelector('button[type="submit"]');

    if (!monthSelect || !yearInput) return;

    async function calculate() {
        const month = monthSelect.value;
        const year = yearInput.value;
        if (!month || !year || year.length !== 4) return;
        if (submitBtn) submitBtn.disabled = true;

        try {
            const url = `${PAYROLL_URLS.calculate}?month=${month}&year=${year}`;
            const response = await fetch(url);
            const data = await safeJsonParse(response);

            if (data.status === 'success') {
                if (startDateInput) startDateInput.value = data.start_date;
                if (endDateInput) endDateInput.value = data.end_date;
                if (workingDaysInput) workingDaysInput.value = data.working_days;

                if (data.warning || data.info) {
                    Swal.fire({
                        title: data.warning ? 'Feriados' : 'Info',
                        text: data.warning || data.info,
                        icon: data.warning ? 'warning' : 'info',
                        scrollbarPadding: false, heightAuto: false
                    });
                }
            }
        } catch (e) {
            console.error("Error:", e);
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    }

    $(monthSelect).on('change.select2', calculate);
    yearInput.addEventListener('change', calculate);
    yearInput.addEventListener('input', function () {
        this.value = this.value.replace(/[^0-9]/g, '').slice(0, 4);
        if (this.value.length === 4) calculate();
    });
    setTimeout(calculate, 300);
};

// LA MAGIA DE LOS RUBROS
window.initializeRubricModal = function (root) {
    const $typeSelect = $(root).find('select[name="rubric_type"]');

    const divPriority = root.querySelector('#divPriority');
    const divIncomeSwitches = root.querySelector('#divIncomeSwitches');
    const divOrder = root.querySelector('#divOrder');
    const divName = root.querySelector('#divName'); // Capturamos el contenedor del Nombre

    function toggleRubricFields() {
        if (!$typeSelect.length) return;
        const val = ($typeSelect.val() || '').toUpperCase();

        // 1. Ocultar todos los campos dinámicos por defecto
        if (divPriority) divPriority.classList.add('hidden-field');
        if (divIncomeSwitches) divIncomeSwitches.classList.add('hidden-field');

        // 2. Restaurar tamaños base de la grilla (Nombre al 66%, Prioridad oculta al 33%)
        if (divName) divName.className = 'col-md-8 form-group';
        if (divPriority) divPriority.className = 'col-md-4 form-group hidden-field';
        if (divOrder) divOrder.className = 'col-md-4 form-group';

        // 3. Mostrar u Ocultar según la selección
        if (val.includes('INCOME') || val === 'INGRESO' || val === '1') {
            // Es Ingreso: Mostrar bloque de 3 switches
            if (divIncomeSwitches) divIncomeSwitches.classList.remove('hidden-field');
        } else if (val.includes('DEDUCTION') || val === 'DESCUENTO' || val === '2') {
            // Es Descuento: Mostramos la prioridad y encogemos el nombre
            if (divPriority) {
                divPriority.classList.remove('hidden-field');
            }
            if (divName) {
                divName.className = 'col-md-4 form-group'; // Encogemos a 33.33%
            }
        }
        // Si es Aporte, se queda como el default (Nombre al 66.67%, lo demás oculto)
    }

    if ($typeSelect.length) {
        $typeSelect.on('change.select2 change', toggleRubricFields);
        setTimeout(toggleRubricFields, 100);
    }
};
/* =================================================================================
   4. LÓGICA DE FONDOS DE RESERVA
   ================================================================================= */
document.addEventListener('change', function (e) {
    const input = e.target;
    if (!input.classList.contains('fr-checkbox')) return;

    const personId = input.dataset.personId;
    const field = input.dataset.field;
    if (!personId || !field) return;

    const wrapper = document.querySelector(`label[for="${input.id || ''}"]`);
    const textEl = wrapper && wrapper.querySelector('.modern-toggle-text');
    const checked = input.checked;

    if (checked) {
        if (wrapper) wrapper.classList.add('modern-toggle-green');
        if (textEl) textEl.textContent = 'Mensualiza';
    } else {
        if (wrapper) wrapper.classList.remove('modern-toggle-green');
        if (textEl) textEl.textContent = 'Acumula';
    }

    const infoUrl = `/employee/person/${personId}/get-payroll-info/`;
    const url = input.dataset.updateUrl || `/employee/person/${personId}/update-payroll-info/`;

    fetch(infoUrl, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(r => r.json())
        .then(infoResp => {
            const current = (infoResp && infoResp.data) ? infoResp.data : {};
            const formData = new FormData();

            const monthly = (field === 'monthly_payment') ? checked : !!current.monthly_payment;
            const reserve = (field === 'reserve_funds' || field === 'fondos_reserva') ? checked : !!current.reserve_funds;

            if (monthly) formData.append('monthly_payment', 'on');
            if (reserve) formData.append('reserve_funds', 'on');

            if (typeof current.family_dependents !== 'undefined') formData.append('family_dependents', String(current.family_dependents));
            if (typeof current.education_dependents !== 'undefined') formData.append('education_dependents', String(current.education_dependents));

            return fetch(url, {
                method: 'POST', body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
            });
        })
        .then(resp => resp.json())
        .then(data => {
            if (!data || data.success === false) {
                input.checked = !checked; // Rollback visual
                Swal.fire('Error', data.message || 'No se pudo actualizar.', 'error');
            }
        }).catch(err => {
        input.checked = !checked;
        Swal.fire('Error', 'Error de comunicación', 'error');
    });
});

/* =================================================================================
   5. DELEGACIÓN DE EVENTOS GLOBAL
   ================================================================================= */
document.addEventListener('click', function (e) {
    const btnGen = e.target.closest('[data-generate-id]');
    if (btnGen) {
        e.preventDefault();
        window.openGenerateModal(
            btnGen.getAttribute('data-generate-id'),
            btnGen.getAttribute('data-generate-name'),
            btnGen.getAttribute('data-has-scope-changes') === 'true'
        );
    }

    const btnRep = e.target.closest('[data-report-id]');
    if (btnRep) {
        e.preventDefault();
        window.openReportModal(
            btnRep.getAttribute('data-report-id'),
            btnRep.getAttribute('data-report-name'),
            btnRep.getAttribute('data-report-closed') === 'true'
        );
    }
});