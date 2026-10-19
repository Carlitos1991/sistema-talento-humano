/**
 * ARCHIVO DIGITAL - GESTOR ESPECÍFICO DEL MÓDULO
 * Hereda TableManager, modales y alertas de main.js.
 */

// 1. Carga y despliegue del modal de bitácora de préstamos extraído del detalle del empleado
function openEmployeeLoanHistoryModal(detailUrl, employeeName) {
    fetch(detailUrl, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(response => {
            if (!response.ok) throw new Error('Error al consultar el detalle');
            return response.text();
        })
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const modal = doc.getElementById('archiveLoanHistoryModal');

            if (!modal) {
                window.location.href = detailUrl;
                return;
            }

            let root = document.getElementById('modal-root');
            if (!root) {
                root = document.createElement('div');
                root.id = 'modal-root';
                document.body.appendChild(root);
            }

            root.innerHTML = '';
            root.appendChild(modal);
            modal.classList.remove('hidden');

            document.documentElement.classList.add('no-scroll');
            document.body.classList.add('no-scroll');
        })
        .catch(error => {
            console.error('Error al cargar modal de bitácora:', error);
            window.location.href = detailUrl;
        });
}

// 2. Carga y despliegue del modal de auditoría extraído del detalle del empleado
function openEmployeeAuditModal(detailUrl, employeeName) {
    fetch(detailUrl, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(response => {
            if (!response.ok) throw new Error('Error al consultar el detalle');
            return response.text();
        })
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const modal = doc.getElementById('archiveAuditModal');

            if (!modal) {
                window.location.href = detailUrl;
                return;
            }

            let root = document.getElementById('modal-root');
            if (!root) {
                root = document.createElement('div');
                root.id = 'modal-root';
                document.body.appendChild(root);
            }

            root.innerHTML = '';
            root.appendChild(modal);
            modal.classList.remove('hidden');

            document.documentElement.classList.add('no-scroll');
            document.body.classList.add('no-scroll');
        })
        .catch(error => {
            console.error('Error al cargar modal de auditoría:', error);
            window.location.href = detailUrl;
        });
}

// 3. Pestañas de tipos de documentos en el detalle
function switchArchiveDocumentTab(targetId) {
    document.querySelectorAll('.archive-tab-btn').forEach(btn => {
        btn.classList.toggle('is-active', btn.dataset.tabTarget === targetId);
    });
    document.querySelectorAll('.archive-tab-pane').forEach(pane => {
        pane.classList.toggle('is-active', pane.id === targetId);
    });
}

// 4. Inicialización de eventos al cargar el DOM
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

    // Buscador con debounce hacia Django
    const searchInput = document.getElementById('table-search');
    if (searchInput) {
        let timer = null;
        searchInput.addEventListener('input', function () {
            clearTimeout(timer);
            timer = setTimeout(() => {
                if (typeof refreshCurrentTable === 'function') {
                    refreshCurrentTable({q: this.value.trim(), page: 1});
                }
            }, 450);
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

    // Input directo de página en la paginación
    document.addEventListener('change', function (e) {
        if (e.target && e.target.id === 'archivePageInput') {
            const page = parseInt(e.target.value) || 1;
            if (typeof refreshCurrentTable === 'function') {
                refreshCurrentTable({page: page});
            }
        }
    });

    // Pestañas del detalle de empleado
    const tabButtons = document.querySelectorAll('.archive-tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', function () {
            switchArchiveDocumentTab(this.dataset.tabTarget);
        });
    });
});

window.openEmployeeLoanHistoryModal = openEmployeeLoanHistoryModal;
window.openEmployeeAuditModal = openEmployeeAuditModal;
window.switchArchiveDocumentTab = switchArchiveDocumentTab;