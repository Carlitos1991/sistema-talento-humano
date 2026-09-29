/**
 * SIGETH - Módulo de Catálogos (Core)
 * Controlador Vanilla JavaScript con delegación limpia y TableManager.
 */

document.addEventListener('DOMContentLoaded', () => {
    const catalogManager = new CatalogManager();
    catalogManager.init();
});

class CatalogManager {
    constructor() {
        this.searchInput = document.getElementById('table-search');
        this.searchTimer = null;
    }

    init() {
        this.bindSearch();
        this.bindStatCards();
        this.bindActionDelegation();
        this.ensureTableManager();
    }

    ensureTableManager() {
        const table = document.querySelector('.managed-table');
        if (table && window.TableManager && !table._tableManager) {
            new window.TableManager(table);
        }
    }

    bindSearch() {
        if (!this.searchInput) return;

        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => {
                const query = e.target.value.trim().toLowerCase();
                const table = document.querySelector('.managed-table');
                if (table && table._tableManager) {
                    table._tableManager.filterState.search = query;
                    table._tableManager.applyGlobalFilters();
                }
            }, 300);
        });
    }

    bindStatCards() {
        const cards = document.querySelectorAll('#catalog-stats-row .stat-card');
        cards.forEach((card) => {
            card.addEventListener('click', () => {
                const filterVal = card.getAttribute('data-filter');

                cards.forEach((c) => {
                    if (c === card) {
                        c.classList.remove('opacity-low');
                    } else {
                        c.classList.add('opacity-low');
                    }
                });

                const table = document.querySelector('.managed-table');
                if (table && table._tableManager) {
                    table._tableManager.filterByColumnData('status', filterVal);
                }
            });
        });
    }

    bindActionDelegation() {
        document.addEventListener('click', (event) => {
            const btn = event.target.closest('[data-action]');
            if (!btn) return;

            const action = btn.dataset.action;
            const modalUrl = btn.dataset.modalUrl;

            // 1. Crear catálogo
            if (action === 'create-catalog' && modalUrl) {
                event.preventDefault();
                window.openAjaxModal(modalUrl, (root) => {
                    this.setupFormModal(root, () => {
                        window.closeModal();
                        window.refreshCurrentTable({}, () => this.ensureTableManager());
                    });
                });
                return;
            }

            // 2. Formulario de Ítems (Crear / Editar)
            if ((action === 'add-item' || action === 'edit-item') && modalUrl) {
                event.preventDefault();
                const catalogId = btn.dataset.catalogId;
                window.openAjaxModal(modalUrl, (root) => {
                    this.setupFormModal(root, () => {
                        // Reabrir lista de ítems actualizada
                        window.openAjaxModal(`/core/catalogs/${catalogId}/items/modal/`, (listRoot) => {
                            const table = listRoot.querySelector('.modal-table');
                            if (table && window.TableManager) new window.TableManager(table);
                        });
                    });
                });
            }
        });
    }

    setupFormModal(modalRoot, successCallback) {
        const form = modalRoot.querySelector('form');
        if (!form) return;

        form.addEventListener('submit', (e) => {
            window.submitAjaxForm(e, (data) => {
                if (typeof successCallback === 'function') {
                    successCallback(data);
                }
            });
        });
    }
}