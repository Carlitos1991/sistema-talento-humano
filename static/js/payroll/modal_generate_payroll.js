// static/js/payroll/modal_generate_payroll.js

let currentGenPeriodId = null;

// Funciones para abrir/cerrar modales de procesamiento y reportes
window.openGenerateModal = function (id, name) {
    currentGenPeriodId = id;
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        document.getElementById('gen-period-name').innerText = name;
        modal.style.display = 'flex';
    }
};

window.closeGenerateModal = function () {
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) modal.style.display = 'none';
};

window.openReportModal = function (id, name, isClosed) {
    currentGenPeriodId = id;
    const modal = document.getElementById('modalReportOptions');
    if (modal) {
        document.getElementById('rep-period-name').innerText = name;
        // El contenedor del sello solo se ve si el periodo NO está cerrado
        const sellarBtn = document.getElementById('sellar-container');
        if (sellarBtn) sellarBtn.style.display = isClosed ? 'none' : 'block';
        modal.style.display = 'flex';
    }
};

window.closeReportModal = function () {
    const modal = document.getElementById('modalReportOptions');
    if (modal) modal.style.display = 'none';
};