/**
 * ARCHIVO DIGITAL - GESTOR ESPECÍFICO DEL MÓDULO
 * La carga de modales, alertas y ordenamiento se delegan a main.js.
 */

// 1. Pestañas en la vista de detalle de archivo digital
function switchArchiveDocumentTab(targetId) {
    document.querySelectorAll('.archive-tab-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.tabTarget === targetId);
    });
    document.querySelectorAll('.archive-tab-pane').forEach(pane => {
        pane.classList.toggle('is-active', pane.id === targetId);
    });
}

// 2. Inicialización de eventos específicos al cargar el DOM
document.addEventListener('DOMContentLoaded', function () {
    // Switch Server-Side de expedientes prestados
    const loanedSwitch = document.getElementById('toggleLoanedExpedients');
    if (loanedSwitch) {
        loanedSwitch.addEventListener('change', function () {
            if (typeof refreshCurrentTable === 'function') {
                refreshCurrentTable({show_loaned: this.checked ? 'true' : 'false', page: 1});
            }
        });
    }

    // Buscador Server-Side con debounce hacia Django
    const searchInput = document.getElementById('table-search');
    if (searchInput) {
        let timer = null;
        searchInput.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(() => {
                if (typeof refreshCurrentTable === 'function') {
                    refreshCurrentTable({q: this.value.trim(), page: 1});
                }
            }, 400);
        });

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                clearTimeout(timer);
                if (typeof refreshCurrentTable === 'function') {
                    refreshCurrentTable({q: this.value.trim(), page: 1});
                }
            }
        });
    }

    // Input numérico directo de página en la paginación Server-Side
    document.addEventListener('change', function (e) {
        if (e.target && e.target.id === 'archivePageInput') {
            const page = parseInt(e.target.value, 10) || 1;
            if (typeof refreshCurrentTable === 'function') {
                refreshCurrentTable({page: page});
            }
        }
    });

    // Delegación de clics para las pestañas de tipos de documentos
    const tabButtons = document.querySelectorAll('.archive-tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            switchArchiveDocumentTab(this.dataset.tabTarget);
        });
    });
});

window.switchArchiveDocumentTab = switchArchiveDocumentTab;