/**
 * PAYROLL.JS - LÓGICA EXCLUSIVA DEL MÓDULO DE NÓMINA
 */

// 1. Modales Estáticos (Procesar y Reportes)
window.openGenerateModal = function (id, name, hasScopeChanges) {
    window.currentGenPeriodId = id;
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        const nameEl = document.getElementById('gen-period-name');
        if (nameEl && name) nameEl.innerText = name;
        modal.setAttribute('style', 'display: flex !important;');
        document.body.classList.add('modal-open');
    }
};

window.closeGenerateModal = function () {
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        modal.setAttribute('style', 'display: none !important;');
        document.body.classList.remove('modal-open');
    }
};

window.openReportModal = function (id, name, isClosed) {
    window.currentGenPeriodId = id;
    const modal = document.getElementById('modalReportOptions');
    if (modal) {
        const nameEl = document.getElementById('rep-period-name');
        if (nameEl && name) nameEl.innerText = name;

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

// 2. Delegación de eventos para la tabla
document.addEventListener('click', function (e) {
    const btnGen = e.target.closest('[data-generate-id]');
    if (btnGen) {
        e.preventDefault();
        const id = btnGen.getAttribute('data-generate-id');
        const name = btnGen.getAttribute('data-generate-name');
        const scope = btnGen.getAttribute('data-has-scope-changes') === 'true';
        if (window.openGenerateModal) window.openGenerateModal(id, name, scope);
    }

    const btnRep = e.target.closest('[data-report-id]');
    if (btnRep) {
        e.preventDefault();
        const id = btnRep.getAttribute('data-report-id');
        const name = btnRep.getAttribute('data-report-name');
        const isClosed = btnRep.getAttribute('data-report-closed');
        if (window.openReportModal) window.openReportModal(id, name, isClosed);
    }
});

// 3. Feriados (Modal de Períodos)
window.initializePeriodModal = function (root) {
    console.log("=> Modal de periodo inyectado y detectado");

    // Selectores más amplios para evitar que Django los esconda
    const monthSelect = root.querySelector('[name="month"]');
    const yearInput = root.querySelector('[name="year"]');
    const startDateInput = root.querySelector('[name="start_date"]');
    const endDateInput = root.querySelector('[name="end_date"]');
    const workingDaysInput = root.querySelector('[name="working_days"]');
    const submitBtn = root.querySelector('button[type="submit"]');

    if (!monthSelect || !yearInput) {
        console.warn("=> No se encontraron los campos de Mes/Año");
        return;
    }

    async function calculateWorkingDays() {
        console.log("=> Iniciando cálculo de días laborables...");
        const month = monthSelect.value;
        const year = yearInput.value;

        if (!month || !year || year.length !== 4) return;
        if (submitBtn) submitBtn.disabled = true;

        try {
            const url = `/payroll/api/calculate-working-days/?month=${encodeURIComponent(month)}&year=${encodeURIComponent(year)}`;
            const response = await fetch(url);

            if (!response.ok) throw new Error("Error en la respuesta del servidor");

            const data = await response.json();
            console.log("=> Respuesta de la API:", data);

            if (data.status === 'success') {
                if (startDateInput) startDateInput.value = data.start_date;
                if (endDateInput) endDateInput.value = data.end_date;
                if (workingDaysInput) workingDaysInput.value = data.working_days;

                if (submitBtn) submitBtn.disabled = false;

                if (data.warning) {
                    Swal.fire({
                        title: 'Feriados Detectados',
                        text: data.warning,
                        icon: 'warning',
                        showCloseButton: true
                    });
                } else if (data.info) {
                    Swal.fire({title: 'Información', text: data.info, icon: 'info', showCloseButton: true});
                }
            } else {
                Swal.fire('Error', 'No se pudieron calcular los días laborables.', 'error');
            }
        } catch (error) {
            console.error("=> Error de conexión AJAX:", error);
            Swal.fire('Error de Red', 'No se pudo contactar al servidor para el cálculo', 'error');
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    }

    $(monthSelect).on('change.select2', calculateWorkingDays);
    yearInput.addEventListener('change', calculateWorkingDays);

    yearInput.addEventListener('input', function () {
        this.value = this.value.replace(/[^0-9]/g, '').slice(0, 4);
        if (this.value.length === 4) calculateWorkingDays();
    });

    // Si es nuevo (el campo de fecha está vacío), calcular a los 300ms
    if (!startDateInput || !startDateInput.value) {
        console.log("=> Periodo nuevo detectado. Ejecutando cálculo automático...");
        setTimeout(calculateWorkingDays, 300);
    }
};