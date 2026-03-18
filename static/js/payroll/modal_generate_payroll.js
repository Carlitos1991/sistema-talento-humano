// static/js/payroll/modal_generate_payroll.js

let currentGenPeriodId = null;

// Funciones para abrir/cerrar modales de procesamiento y reportes
window.openGenerateModal = function (id, name, userInitiated) {
    // Sólo permitir apertura si fue iniciada por el usuario (evita auto-disparos al cargar)
    if (typeof userInitiated === 'undefined') userInitiated = false;
    if (!userInitiated) return;
    currentGenPeriodId = id;
    const modal = document.getElementById('modalGeneratePayroll');
    if (modal) {
        document.getElementById('gen-period-name').innerText = name;
        modal.style.display = 'flex';
        // marcar body como modal-open para evitar scrolling del fondo
        try { document.body.classList.add('modal-open'); } catch(e){}
        // Asegurar que el botón de cerrar sea visible (algunos scripts pueden ocultarlo momentáneamente)
        try {
            const btn = modal.querySelector('.btn-close-modal, .btn-close-modal-refined');
            if (btn) { btn.style.display = 'inline-block'; btn.style.opacity = '1'; }
            // Re-aplicar visibilidad varias veces en los primeros 600ms
            let tries = 0;
            const enforce = setInterval(() => {
                try { if (btn) { btn.style.display = 'inline-block'; btn.style.opacity = '1'; btn.style.visibility = 'visible'; btn.style.pointerEvents = 'auto'; btn.style.zIndex = '9999'; } } catch(e){}
                tries += 1;
                if (tries > 6) clearInterval(enforce);
            }, 100);
        } catch(e){}
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