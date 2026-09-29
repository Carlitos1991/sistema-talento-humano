/**
 * SIGETH - Módulo de Sanciones
 * Manejo de pestañas, búsqueda reactiva de empleados, filtros de fecha,
 * filtrado por tarjetas estadísticas (stats) y modales AJAX universales.
 */
document.addEventListener('DOMContentLoaded', () => {

    const listUrl = window.location.pathname;
    let currentStatusFilter = 'all';

    /* =========================================================================
       1. MANEJO DE PESTAÑAS (TABS)
       ========================================================================= */
    const tabButtons = document.querySelectorAll('.sanctions-tab-btn');
    const tabPanes = document.querySelectorAll('.sanctions-tab-pane');

    function switchTab(tabName, persist = true) {
        tabButtons.forEach(btn => {
            const isActive = btn.dataset.sanctionsTab === tabName;
            btn.classList.toggle('is-active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        tabPanes.forEach(pane => {
            const isActive = pane.dataset.sanctionsPane === tabName;
            pane.classList.toggle('is-active', isActive);
            pane.style.display = isActive ? 'block' : 'none';
        });

        if (persist) {
            window.localStorage.setItem('sanctions-active-tab', tabName);
        }
    }

    if (tabButtons.length && tabPanes.length) {
        const storedTab = window.localStorage.getItem('sanctions-active-tab') || 'employees';
        switchTab(storedTab, false);

        tabButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                switchTab(btn.dataset.sanctionsTab, true);
            });
        });
    }

    /* =========================================================================
       2. BÚSQUEDA REACTIVA - PESTAÑA EMPLEADOS
       ========================================================================= */
    const employeeSearch = document.getElementById('employee-search');

    function fetchEmployees(page = 1, query = null) {
        const q = query !== null ? query : (employeeSearch ? employeeSearch.value.trim() : '');
        const params = new URLSearchParams();
        params.set('page', page);
        if (q) params.set('q', q);

        fetch(`${listUrl}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                const wrapper = document.getElementById('table-content-wrapper');
                if (wrapper && data.html) {
                    wrapper.innerHTML = data.html;
                }
            })
            .catch(err => console.error('Error cargando empleados:', err));
    }

    if (employeeSearch) {
        let debounceTimer;
        employeeSearch.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                fetchEmployees(1, e.target.value.trim());
            }, 300);
        });
    }

    /* =========================================================================
       3. FILTROS, BÚSQUEDA Y STATS - PESTAÑA NOTIFICACIONES
       ========================================================================= */
    const notifSearch = document.getElementById('notifications-search');
    const notifMonth = document.getElementById('notifications-month');
    const notifYear = document.getElementById('notifications-year');

    function fetchNotifications(page = 1) {
        const params = new URLSearchParams();
        params.set('section', 'notifications'); // Requerido por EmployeeSanctionListView
        params.set('notifications_page', page);

        if (currentStatusFilter && currentStatusFilter !== 'all') {
            params.set('status_filter', currentStatusFilter);
        } else {
            params.set('status_filter', 'all');
        }

        const q = notifSearch ? notifSearch.value.trim() : '';
        if (q) params.set('notifications_q', q);

        if (notifMonth && notifMonth.value) {
            params.set('notifications_month', notifMonth.value);
        }
        if (notifYear && notifYear.value) {
            params.set('notifications_year', notifYear.value);
        }

        fetch(`${listUrl}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                const wrapper = document.getElementById('latest-notifications-wrapper');
                if (wrapper && data.html) {
                    wrapper.innerHTML = data.html;
                }

                // Actualizar tarjetas de estadísticas numéricas superiores
                if (data.stats && Array.isArray(data.stats)) {
                    updateStatsCards(data.stats);
                }
            })
            .catch(err => console.error('Error cargando notificaciones:', err));
    }

    function updateStatsCards(statsList) {
        const statsContainer = document.querySelector('[data-sanctions-pane="notifications"] .stats-row');
        if (!statsContainer) return;

        statsContainer.innerHTML = '';
        statsList.forEach(stat => {
            const card = document.createElement('div');
            card.className = `stat-card ${stat.class || ''} js-notification-stat-filter`.trim();
            card.dataset.filterVal = stat.filter_val;
            card.style.cursor = 'pointer';

            // Destacar visualmente la tarjeta activa
            if (stat.filter_val === currentStatusFilter || (currentStatusFilter === 'all' && stat.filter_val === 'all')) {
                card.style.transform = 'translateY(-3px)';
                card.style.boxShadow = '0 8px 24px rgba(15, 23, 42, 0.12)';
                card.style.borderColor = '#10b981';
            }

            card.innerHTML = `
                <div class="stat-left">
                    <h3>${stat.label}</h3>
                    <div class="number">${stat.count}</div>
                </div>
                <i class="fas ${stat.icon || 'fa-circle'} stat-icon"></i>
            `;
            statsContainer.appendChild(card);
        });
    }

    // Input de búsqueda de notificaciones con debounce
    if (notifSearch) {
        let notifTimer;
        notifSearch.addEventListener('input', () => {
            clearTimeout(notifTimer);
            notifTimer = setTimeout(() => fetchNotifications(1), 300);
        });
    }

    if (notifMonth) notifMonth.addEventListener('change', () => fetchNotifications(1));
    if (notifYear) notifYear.addEventListener('change', () => fetchNotifications(1));

    // Clic en tarjetas de estadísticas
    document.addEventListener('click', (e) => {
        const statCard = e.target.closest('.js-notification-stat-filter');
        if (!statCard) return;

        currentStatusFilter = statCard.dataset.filterVal || 'all';
        fetchNotifications(1);
    });

    /* =========================================================================
       4. PAGINACIÓN DE AMBAS TABLAS (DELEGACIÓN)
       ========================================================================= */
    document.addEventListener('click', (e) => {
        const pageBtn = e.target.closest('.page-btn');
        if (!pageBtn || pageBtn.disabled) return;

        const targetPage = parseInt(pageBtn.dataset.page, 10);
        if (isNaN(targetPage)) return;

        const inNotifications = pageBtn.closest('#latest-notifications-wrapper') || pageBtn.closest('#js-pagination-notifications');
        if (inNotifications) {
            e.preventDefault();
            fetchNotifications(targetPage);
        } else {
            e.preventDefault();
            fetchEmployees(targetPage);
        }
    });

    document.addEventListener('change', (e) => {
        if (!e.target.matches('.page-input')) return;

        const targetPage = parseInt(e.target.value, 10);
        if (isNaN(targetPage) || targetPage < 1) return;

        const inNotifications = e.target.closest('#latest-notifications-wrapper') || e.target.closest('#js-pagination-notifications');
        if (inNotifications) {
            fetchNotifications(targetPage);
        } else {
            fetchEmployees(targetPage);
        }
    });

    /* =========================================================================
       5. GESTIÓN DE MODALES VÍA MAIN.JS (openAjaxModal)
       ========================================================================= */
    document.addEventListener('click', (e) => {
        const btnModal = e.target.closest('.js-sanction-modal-btn');
        if (btnModal) {
            e.preventDefault();
            const targetUrl = btnModal.dataset.url;
            if (targetUrl && typeof window.openAjaxModal === 'function') {
                window.openAjaxModal(targetUrl);
            }
            return;
        }

        // Toggle respuesta (¿Ha respondido?)
        const btnToggleResponse = e.target.closest('.js-toggle-response');
        if (btnToggleResponse) {
            e.preventDefault();
            const notifId = btnToggleResponse.dataset.id;
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

            fetch(`/sanctions/notifications/${notifId}/toggle-response/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        const textSpan = btnToggleResponse.querySelector('.modern-toggle-text');
                        if (textSpan) textSpan.textContent = data.label;
                        btnToggleResponse.classList.toggle('modern-toggle-green', data.has_responded);
                    }
                })
                .catch(err => console.error('Error toggling response:', err));
        }
    });

    // Envío de formularios dentro de modales (refresca la pestaña que esté activa)
    document.addEventListener('submit', (e) => {
        const form = e.target;
        if (form.matches('#generateSanctionForm, #generateNotificationForm, #form-set-notified, #sanctionTypeForm, .ajax-sanction-form')) {
            if (typeof window.submitAjaxForm === 'function') {
                window.submitAjaxForm(e, () => {
                    const activeTab = window.localStorage.getItem('sanctions-active-tab') || 'employees';
                    if (activeTab === 'notifications') {
                        fetchNotifications(1);
                    } else {
                        fetchEmployees(1);
                    }
                });
            }
        }
    });

});