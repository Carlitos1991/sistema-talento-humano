/**
 * SIGETH - Asignación de Horarios a Empleados
 * Controlador Vanilla JavaScript basado en el estándar corporativo.
 */

document.addEventListener('DOMContentLoaded', () => {
    const assignmentManager = new ScheduleAssignmentManager();
    assignmentManager.init();
});

class ScheduleAssignmentManager {
    constructor() {
        this.tableWrapper = document.getElementById('table-content-wrapper');
        this.searchInput = document.getElementById('table-search');
        this.searchTimer = null;
    }

    init() {
        this.bindSearch();
        this.bindTableEvents();
        this.ensureTableManager();
    }

    ensureTableManager() {
        const table = document.querySelector('.managed-table');
        if (table && window.TableManager && !table._tableManager) {
            new window.TableManager(table);
        }
    }

    /**
     * Búsqueda en servidor con debounce mediante refreshCurrentTable
     */
    bindSearch() {
        if (!this.searchInput) return;

        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => {
                const query = e.target.value.trim();
                window.refreshCurrentTable({q: query, page: 1}, () => {
                    this.ensureTableManager();
                });
            }, 300);
        });
    }

    /**
     * Delegación de clics sobre la tabla para abrir modales dinámicos
     */
    bindTableEvents() {
        if (!this.tableWrapper) return;

        this.tableWrapper.addEventListener('click', (event) => {
            // 1. Ver historial de asignaciones
            const historyBtn = event.target.closest('.js-view-schedule-history');
            if (historyBtn) {
                event.preventDefault();
                const employeeId = historyBtn.dataset.employeeId;
                window.openAjaxModal(`/schedule/assignment/history/${employeeId}/`);
                return;
            }

            // 2. Asignar o Cambiar Horario
            const changeBtn = event.target.closest('.js-change-schedule');
            if (changeBtn) {
                event.preventDefault();
                const employeeId = changeBtn.dataset.employeeId;
                window.openAjaxModal(`/schedule/assignment/change-modal/${employeeId}/`, (root) => {
                    this.setupFormModal(root);
                });
            }
        });
    }

    /**
     * Vinculación de eventos al inyectar el formulario modal en el DOM
     * @param {HTMLElement} modalRoot
     */
    setupFormModal(modalRoot) {
        const form = modalRoot.querySelector('#employee-schedule-form');
        if (!form) return;

        form.addEventListener('submit', (e) => {
            window.submitAjaxForm(e, () => {
                window.closeModal();
                window.refreshCurrentTable({}, () => {
                    this.ensureTableManager();
                });
            });
        });
    }
}