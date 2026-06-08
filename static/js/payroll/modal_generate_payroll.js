// static/js/payroll/modal_generate_payroll.js

let currentGenPeriodId = null;

window.openGenerateModal = function (id, name, hasScopeChanges) {
    currentGenPeriodId = id;
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        const nameEl = document.getElementById('gen-period-name');
        if (nameEl && name) nameEl.innerText = name;

        const scopeButton = document.getElementById('btn-generate-scope');
        if (scopeButton) {
            scopeButton.style.display = hasScopeChanges ? 'flex' : 'none';
        }

        // Forzamos la visibilidad y bloqueamos el scroll del fondo
        modal.setAttribute('style', 'display: flex !important;');
        document.body.classList.add('modal-open');
    }
};

window.closeGenerateModal = function () {
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        // Volvemos a ocultar fuertemente y liberamos el fondo
        modal.setAttribute('style', 'display: none !important;');
        document.body.classList.remove('modal-open');
    }
};

window.openReportModal = function (id, name, isClosed) {
    currentGenPeriodId = id;
    const modal = document.getElementById('modalReportOptions');
    if (modal) {
        const nameEl = document.getElementById('rep-period-name');
        if (nameEl && name) nameEl.innerText = name;

        const sellarBtn = document.getElementById('sellar-container');
        if (sellarBtn) sellarBtn.style.display = isClosed ? 'none' : 'block';

        // Forzamos la visibilidad y bloqueamos el scroll del fondo
        modal.setAttribute('style', 'display: flex !important;');
        document.body.classList.add('modal-open');
    }
};

window.closeReportModal = function () {
    const modal = document.getElementById('modalReportOptions');
    if (modal) {
        // Volvemos a ocultar fuertemente y liberamos el fondo
        modal.setAttribute('style', 'display: none !important;');
        document.body.classList.remove('modal-open');
    }
};
