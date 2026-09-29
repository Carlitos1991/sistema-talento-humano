/**
 * SIGETH - Módulo de Horarios (Schedule)
 * Controlador Vanilla JavaScript para listado y modales AJAX dinámicos.
 */

document.addEventListener('DOMContentLoaded', () => {
    const scheduleManager = new ScheduleManager();
    scheduleManager.init();
});

class ScheduleManager {
    constructor() {
        this.tableWrapper = document.getElementById('table-content-wrapper');
        this.searchInput = document.getElementById('table-search');
        this.searchTimer = null;
    }

    init() {
        this.bindSearch();
        this.bindTableEvents();
        this.bindCreateButton();
        this.ensureTableManager();
    }

    /**
     * Asegura la inicialización de TableManager sobre la tabla activa
     */
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
     * Abrir modal de creación vía openAjaxModal de main.js
     */
    bindCreateButton() {
        const btnCreate = document.getElementById('btn-create-schedule');
        if (btnCreate) {
            btnCreate.addEventListener('click', () => {
                window.openAjaxModal('/schedule/modal/form/', (root) => {
                    this.setupModalEvents(root);
                });
            });
        }
    }

    /**
     * Delegación de clics sobre la tabla para editar, ver historial y dar de alta/baja
     */
    bindTableEvents() {
        if (!this.tableWrapper) return;

        this.tableWrapper.addEventListener('click', (event) => {
            // 1. Editar Horario
            const editBtn = event.target.closest('.js-btn-edit');
            if (editBtn) {
                event.preventDefault();
                const scheduleId = editBtn.dataset.id;
                window.openAjaxModal(`/schedule/modal/form/${scheduleId}/`, (root) => {
                    this.setupModalEvents(root);
                });
                return;
            }

            // 2. Historial de Versiones
            const historyBtn = event.target.closest('.js-btn-history');
            if (historyBtn) {
                event.preventDefault();
                const scheduleId = historyBtn.dataset.id;
                window.openAjaxModal(`/schedule/history/${scheduleId}/`);
                return;
            }

            // 3. Activar / Desactivar (Toggle)
            const toggleBtn = event.target.closest('.js-btn-toggle');
            if (toggleBtn) {
                event.preventDefault();
                const url = toggleBtn.dataset.url;
                const name = toggleBtn.dataset.name;
                const currentStatus = toggleBtn.dataset.status === 'true';

                window.toggleStatusAjax(url, `el horario "${name}"`, currentStatus, () => {
                    window.refreshCurrentTable({}, () => {
                        this.ensureTableManager();
                    });
                });
            }
        });
    }

    /**
     * Configuración del formulario inyectado en modal-root
     * @param {HTMLElement} modalRoot
     */
    setupModalEvents(modalRoot) {
        const form = modalRoot.querySelector('#scheduleForm');
        if (!form) return;

        // Envío AJAX corporativo
        form.addEventListener('submit', (e) => {
            window.submitAjaxForm(e, () => {
                window.closeModal();
                window.refreshCurrentTable({}, () => {
                    this.ensureTableManager();
                });
            });
        });

        // Matriz interactiva de días
        const daysMatrix = modalRoot.querySelector('#daysMatrixContainer');
        if (daysMatrix) {
            daysMatrix.addEventListener('click', (e) => {
                const item = e.target.closest('.day-item');
                if (!item) return;

                const checkbox = item.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    checkbox.checked = !checkbox.checked;
                    item.classList.toggle('active', checkbox.checked);
                }
            });
        }

        // Entradas de tiempo para recálculo automático
        const timeInputs = form.querySelectorAll(
            'input[name="morning_start"], input[name="morning_end"], input[name="morning_crosses_midnight"], ' +
            'input[name="afternoon_start"], input[name="afternoon_end"], input[name="afternoon_crosses_midnight"]'
        );

        timeInputs.forEach((input) => {
            input.addEventListener('change', () => this.calculateDailyHours(form));
            input.addEventListener('input', () => this.calculateDailyHours(form));
        });

        this.calculateDailyHours(form);
    }

    /**
     * Recálculo automático de horas en base a las dos jornadas
     * @param {HTMLFormElement} form
     */
    calculateDailyHours(form) {
        const morningStart = form.querySelector('input[name="morning_start"]')?.value;
        const morningEnd = form.querySelector('input[name="morning_end"]')?.value;
        const morningCrosses = form.querySelector('input[name="morning_crosses_midnight"]')?.checked;

        const afternoonStart = form.querySelector('input[name="afternoon_start"]')?.value;
        const afternoonEnd = form.querySelector('input[name="afternoon_end"]')?.value;
        const afternoonCrosses = form.querySelector('input[name="afternoon_crosses_midnight"]')?.checked;

        const dailyHoursInput = form.querySelector('#id_daily_hours') || form.querySelector('input[name="daily_hours"]');

        let total = 0;
        if (morningStart && morningEnd) {
            total += this.calculateTimeDiff(morningStart, morningEnd, morningCrosses);
        }
        if (afternoonStart && afternoonEnd) {
            total += this.calculateTimeDiff(afternoonStart, afternoonEnd, afternoonCrosses);
        }

        const calculated = Math.max(0, parseFloat(total.toFixed(2)));
        if (dailyHoursInput) {
            dailyHoursInput.value = calculated.toFixed(2);
        }
    }

    /**
     * Diferencia matemática entre horas HH:mm
     */
    calculateTimeDiff(start, end, crossesMidnight) {
        if (!start || !end) return 0;

        const [startHours, startMinutes] = start.split(':').map(Number);
        const [endHours, endMinutes] = end.split(':').map(Number);

        const startDate = new Date(2000, 0, 1, startHours, startMinutes);
        let endDate = new Date(2000, 0, 1, endHours, endMinutes);

        if (crossesMidnight || endDate <= startDate) {
            endDate.setDate(endDate.getDate() + 1);
        }

        const diffMs = endDate - startDate;
        const decimal = diffMs / (1000 * 60 * 60);
        return decimal > 0 ? decimal : 0;
    }
}