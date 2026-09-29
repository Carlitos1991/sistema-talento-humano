/**
 * SIGETH - Módulo de Feriados y Observaciones
 * Controlador Vanilla JavaScript basado en el estándar de distributivo presupuestario.
 */

document.addEventListener('DOMContentLoaded', () => {
    const observationManager = new ObservationManager();
    observationManager.init();
});

class ObservationManager {
    constructor() {
        this.tableWrapper = document.getElementById('table-content-wrapper');
        this.searchInput = document.getElementById('table-search');
        this.searchTimer = null;
        this.currentFilter = '';
    }

    init() {
        this.bindSearch();
        this.bindStatCards();
        this.bindTableEvents();
        this.bindCreateButton();
        this.ensureTableManager();
    }

    ensureTableManager() {
        const table = document.querySelector('.managed-table');
        if (table && window.TableManager && !table._tableManager) {
            new window.TableManager(table);
        }
    }

    /**
     * Búsqueda en servidor con debounce
     */
    bindSearch() {
        if (!this.searchInput) return;

        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => {
                this.refreshList(1);
            }, 300);
        });
    }

    /**
     * Tarjetas de estadísticas con alternancia de opacidad (opacity-low)
     */
    bindStatCards() {
        const cards = document.querySelectorAll('#observation-stats-row .stat-card');
        cards.forEach((card) => {
            card.addEventListener('click', () => {
                const filterVal = card.getAttribute('data-filter');
                this.currentFilter = filterVal;

                // Marcar tarjeta activa y atenuar las demás
                cards.forEach((c) => {
                    if (c === card) {
                        c.classList.remove('opacity-low');
                    } else {
                        c.classList.add('opacity-low');
                    }
                });

                this.refreshList(1);
            });
        });
    }

    /**
     * Recarga el fragmento parcial de la tabla vía refreshCurrentTable
     */
    refreshList(page = 1) {
        const query = (this.searchInput?.value || '').trim();
        const params = {
            q: query,
            page: page
        };

        if (this.currentFilter !== '') {
            params.is_holiday = this.currentFilter;
        }

        window.refreshCurrentTable(params, () => {
            this.ensureTableManager();
        });
    }

    /**
     * Abrir modal para crear nuevo feriado u observación
     */
    bindCreateButton() {
        const btnCreate = document.getElementById('btn-create-observation');
        if (btnCreate) {
            btnCreate.addEventListener('click', () => {
                window.openAjaxModal('/schedule/observations/modal/form/', (root) => {
                    this.setupModalEvents(root);
                });
            });
        }
    }

    /**
     * Delegación de clics sobre la tabla
     */
    bindTableEvents() {
        if (!this.tableWrapper) return;

        this.tableWrapper.addEventListener('click', (event) => {
            // 1. Editar registro
            const editBtn = event.target.closest('.js-btn-edit-obs');
            if (editBtn) {
                event.preventDefault();
                const obsId = editBtn.dataset.id;
                window.openAjaxModal(`/schedule/observations/modal/form/${obsId}/`, (root) => {
                    this.setupModalEvents(root);
                });
                return;
            }

            // 2. Dar de alta / baja (Toggle)
            const toggleBtn = event.target.closest('.js-btn-toggle-obs');
            if (toggleBtn) {
                event.preventDefault();
                const url = toggleBtn.dataset.url;
                const name = toggleBtn.dataset.name;
                const currentStatus = toggleBtn.dataset.status === 'true';

                window.toggleStatusAjax(url, `el registro "${name}"`, currentStatus, () => {
                    this.refreshList();
                });
            }
        });
    }

    /**
     * Configuración del formulario dentro del modal
     */
    setupModalEvents(modalRoot) {
        const form = modalRoot.querySelector('#observationForm');
        if (!form) return;

        form.addEventListener('submit', (e) => {
            window.submitAjaxForm(e, () => {
                window.closeModal();
                this.refreshList();
            });
        });
    }
}