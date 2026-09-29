/**
 * SIGETH - Módulo de Ubicaciones (Locations)
 * Vanilla JS sin dependencias de Vue, conectado con main.js.
 */

document.addEventListener('DOMContentLoaded', () => {
    const locationManager = new LocationManager();
    locationManager.init();
});

class LocationManager {
    constructor() {
        this.searchInput = document.getElementById('table-search');
        this.searchTimer = null;
        this.currentFilters = {
            level: '1',
            parent_id: null,
            q: ''
        };
    }

    init() {
        this.bindSearch();
        this.bindStatCards();
        this.bindActionDelegation();
        this.ensureTableManager();
        this.syncLevelHighlight('1');
    }

    ensureTableManager() {
        const table = document.querySelector('.managed-table');
        if (table && window.TableManager && !table._tableManager) {
            new window.TableManager(table);
        }
    }

    syncLevelHighlight(level) {
        const cards = document.querySelectorAll('#location-stats-row .stat-card');
        cards.forEach((card) => {
            const cardLevel = card.getAttribute('data-level');
            if (String(cardLevel) === String(level)) {
                card.classList.remove('opacity-low');
            } else {
                card.classList.add('opacity-low');
            }
        });
    }

    updateDashboardCounters(stats) {
        if (!stats) return;
        const elCountry = document.getElementById('stat-country');
        const elProvince = document.getElementById('stat-province');
        const elCity = document.getElementById('stat-city');
        const elParish = document.getElementById('stat-parish');

        if (elCountry) elCountry.textContent = stats.country;
        if (elProvince) elProvince.textContent = stats.province;
        if (elCity) elCity.textContent = stats.city;
        if (elParish) elParish.textContent = stats.parish;
    }

    bindSearch() {
        if (!this.searchInput) return;

        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => {
                this.currentFilters.q = e.target.value.trim();
                this.loadLocationsTable();
            }, 300);
        });
    }

    bindStatCards() {
        const cards = document.querySelectorAll('#location-stats-row .stat-card');
        cards.forEach((card) => {
            card.addEventListener('click', () => {
                const level = card.getAttribute('data-level');
                this.currentFilters.level = level;
                this.currentFilters.parent_id = null;
                this.syncLevelHighlight(level);
                this.loadLocationsTable();
            });
        });
    }

    loadLocationsTable() {
        const params = new URLSearchParams();
        if (this.currentFilters.parent_id) {
            params.append('parent_id', this.currentFilters.parent_id);
        } else if (this.currentFilters.level) {
            params.append('level', this.currentFilters.level);
        }
        if (this.currentFilters.q) {
            params.append('q', this.currentFilters.q);
        }

        const url = `${window.location.pathname}?${params.toString()}`;

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                const wrapper = document.getElementById('table-content-wrapper');
                if (wrapper && data.html) {
                    wrapper.innerHTML = data.html;
                    this.ensureTableManager();

                    if (data.current_display_level) {
                        this.syncLevelHighlight(data.current_display_level);
                    }
                    if (data.stats) {
                        this.updateDashboardCounters(data.stats);
                    }
                }
            })
            .catch(err => console.error('Error cargando ubicaciones:', err));
    }

    bindActionDelegation() {
        document.addEventListener('click', (event) => {
            // 1. Abrir Modal de creación raíz
            const btnCreateRoot = event.target.closest('[data-action="create-root-location"]');
            if (btnCreateRoot) {
                event.preventDefault();
                const url = btnCreateRoot.dataset.modalUrl;
                window.openAjaxModal(url, (root) => this.setupFormModal(root));
                return;
            }

            // 2. Navegar hacia abajo por clic en el Nombre
            const linkParent = event.target.closest('[data-action="filter-parent"]');
            if (linkParent) {
                event.preventDefault();
                this.currentFilters.parent_id = linkParent.dataset.parentId;
                this.currentFilters.level = null;
                this.loadLocationsTable();
                return;
            }

            // 3. Navegar hacia arriba por Nivel (ej: volver a Países)
            const linkLevel = event.target.closest('[data-action="filter-level"]');
            if (linkLevel) {
                event.preventDefault();
                this.currentFilters.level = linkLevel.dataset.level;
                this.currentFilters.parent_id = null;
                this.syncLevelHighlight(linkLevel.dataset.level);
                this.loadLocationsTable();
            }
        });
    }

    setupFormModal(modalRoot) {
        const form = modalRoot.querySelector('form');
        if (!form) return;

        form.addEventListener('submit', (e) => {
            window.submitAjaxForm(e, (data) => {
                window.closeModal();
                if (data && data.new_stats) {
                    this.updateDashboardCounters(data.new_stats);
                }
                this.loadLocationsTable();
            });
        });
    }
}