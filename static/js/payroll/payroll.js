/**
 * PAYROLL.JS - GESTIÓN INTEGRAL DE NÓMINA
 */

// 1. MAPEADO DE RUTAS (Basado exactamente en urls.py)
const PAYROLL_URLS = {
    // Generación y Recálculo
    recalculate: '/payroll/payslips/recalculate/',      // Recalcular todo / Alcance
    syncMissing: '/payroll/generate/missing/',          // Sincronizar faltantes

    // Acciones de Periodo
    seal: (id) => `/payroll/period/${id}/mark-paid/`,   // Sellar como pagado
    calculate: '/payroll/api/calculate-working-days/',  // Motor de feriados

    // Listados
    tableList: '/payroll/periods/',                     // Recarga de la tabla principal

    // Polling (Nota: Si usas Celery, esta ruta debe existir en tu urls.py)
    status: '/payroll/payslips/recalculate-status/'
};

window.currentGenPeriodId = null;

/**
 * UTILERÍA: Validación de respuestas del servidor
 */
async function safeJsonParse(response) {
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('text/html')) {
        throw new Error(`Error de configuración: El servidor devolvió una página (HTML) en lugar de datos (JSON). Revisa la ruta: ${response.url}`);
    }
    const data = await response.json();
    // En Django, a veces enviamos {status: 'success'} o {success: true}
    if (!response.ok || (data.status === 'error' || data.success === false)) {
        throw new Error(data.message || 'Error en el servidor');
    }
    return data;
}

/**
 * 2. GESTIÓN DE MODALES ESTÁTICOS
 */
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

/**
 * 3. PROCESAMIENTO (Sincronizar, Recalcular, Alcance)
 */
window.submitGenerate = function (mode) {
    const periodId = window.currentGenPeriodId;
    if (!periodId) return;

    document.getElementById('generate-options').style.display = 'none';
    document.getElementById('generate-loading').style.display = 'block';

    const formData = new FormData();
    formData.append('period_id', periodId);

    // Definir URL y parámetros extra según el modo
    let targetUrl = PAYROLL_URLS.recalculate;
    if (mode === 'missing') {
        targetUrl = PAYROLL_URLS.syncMissing;
    } else if (mode === 'scope') {
        formData.append('scope', 'true');
    }

    fetch(targetUrl, {
        method: 'POST',
        body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
    })
        .then(safeJsonParse)
        .then(data => {
            if (data.task_id) {
                startGenerationPolling(data.task_id);
            } else {
                handleGenerationSuccess(data.message || 'Proceso completado.');
            }
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
        didOpen: () => {
            Swal.showLoading();
        }
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
            .catch(err => {
                Swal.fire({icon: 'error', title: 'Error en la tarea', text: err.message});
            });
    };
    poll();
}

function handleGenerationSuccess(message) {
    Swal.fire({
        icon: 'success',
        title: '¡Éxito!',
        text: message,
        timer: 2000,
        showConfirmButton: false,
        scrollbarPadding: false,
        heightAuto: false
    })
        .then(() => {
            window.closeGenerateModal();
            window.reloadTableData(PAYROLL_URLS.tableList, '#period-table-container');
        });
}

/**
 * 4. SELLAR PERIODO (CIERRE)
 */
window.sellarComoPagados = function () {
    const periodId = window.currentGenPeriodId;
    if (!periodId) return;

    Swal.fire({
        title: '¿Sellar periodo?',
        text: "Marcarás todos los roles como pagados y no podrás realizar más cambios.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#10b981',
        confirmButtonText: 'Sí, sellar ahora',
        cancelButtonText: 'Cancelar',
        scrollbarPadding: false,
        heightAuto: false
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(PAYROLL_URLS.seal(periodId), {
                method: 'POST',
                headers: {'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCSRF()}
            })
                .then(safeJsonParse)
                .then(data => {
                    Swal.fire({icon: 'success', title: 'Periodo Cerrado', scrollbarPadding: false, heightAuto: false})
                        .then(() => {
                            window.closeReportModal();
                            window.reloadTableData(PAYROLL_URLS.tableList, '#period-table-container');
                        });
                })
                .catch(err => {
                    Swal.fire('Error', err.message, 'error');
                });
        }
    });
};

/**
 * 5. FORMULARIO DE PERIODO (Cálculo automático de fechas y feriados)
 */
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
            console.error("Error calculando feriados:", e);
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

/**
 * 6. DELEGACIÓN DE EVENTOS
 */
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