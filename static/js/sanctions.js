/**
 * SIGETH - Módulo de Sanciones
 * Pestañas, búsqueda reactiva, selección masiva y paginación limpia.
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
       2. BÚSQUEDA REACTIVA - EMPLEADOS
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
       3. FILTROS, BÚSQUEDA Y STATS - NOTIFICACIONES
       ========================================================================= */
    const notifSearch = document.getElementById('notifications-search');
    const notifMonth = document.getElementById('notifications-month');
    const notifYear = document.getElementById('notifications-year');

    function fetchNotifications(page = 1) {
        const params = new URLSearchParams();
        params.set('section', 'notifications');
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

                if (data.stats && Array.isArray(data.stats)) {
                    updateStatsCards(data.stats);
                }

                updateBulkActionVisibility();
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

            card.innerHTML = `
                <div>
                    <h3>${stat.label}</h3>
                    <div class="number">${stat.count}</div>
                </div>
                <i class="fas ${stat.icon || 'fa-circle'} stat-icon"></i>
            `;
            statsContainer.appendChild(card);
        });
    }

    if (notifSearch) {
        let notifTimer;
        notifSearch.addEventListener('input', () => {
            clearTimeout(notifTimer);
            notifTimer = setTimeout(() => fetchNotifications(1), 300);
        });
    }

    if (notifMonth) notifMonth.addEventListener('change', () => fetchNotifications(1));
    if (notifYear) notifYear.addEventListener('change', () => fetchNotifications(1));

    document.addEventListener('click', (e) => {
        const statCard = e.target.closest('.js-notification-stat-filter');
        if (!statCard) return;

        currentStatusFilter = statCard.dataset.filterVal || 'all';
        fetchNotifications(1);
    });

    /* =========================================================================
       4. CHECKBOXES Y ASIGNACIÓN MASIVA
       ========================================================================= */
    function updateBulkActionVisibility() {
        const bulkBar = document.getElementById('bulk-assign-actions');
        const countSpan = document.getElementById('selected-notifications-count');
        const checkedBoxes = document.querySelectorAll('.js-notification-checkbox:checked');
        const allBoxes = document.querySelectorAll('.js-notification-checkbox');
        const masterCheck = document.getElementById('check-all-notifications');

        const totalSelected = checkedBoxes.length;

        if (bulkBar) {
            if (totalSelected > 0) {
                bulkBar.classList.remove('hidden');
                if (countSpan) countSpan.textContent = `${totalSelected} seleccionado${totalSelected !== 1 ? 's' : ''}`;
            } else {
                bulkBar.classList.add('hidden');
            }
        }

        if (masterCheck && allBoxes.length > 0) {
            masterCheck.checked = (totalSelected === allBoxes.length);
            masterCheck.indeterminate = (totalSelected > 0 && totalSelected < allBoxes.length);
        }
    }

    document.addEventListener('change', (e) => {
        if (e.target && e.target.id === 'check-all-notifications') {
            const isChecked = e.target.checked;
            document.querySelectorAll('.js-notification-checkbox').forEach(chk => chk.checked = isChecked);
            updateBulkActionVisibility();
            return;
        }

        if (e.target && e.target.classList.contains('js-notification-checkbox')) {
            updateBulkActionVisibility();
        }
    });

    document.addEventListener('click', (e) => {
        const btnBulk = e.target.closest('.js-btn-bulk-assign');
        if (!btnBulk) return;

        e.preventDefault();
        const selectedIds = Array.from(document.querySelectorAll('.js-notification-checkbox:checked'))
            .map(chk => chk.dataset.id)
            .filter(Boolean);

        if (selectedIds.length === 0) return;

        const url = `/sanctions/notifications/assign/?ids=${selectedIds.join(',')}`;
        if (typeof window.openAjaxModal === 'function') {
            window.openAjaxModal(url);
        }
    });

    /* =========================================================================
       5. PAGINACIÓN ÚNICA (SIN DUPLICACIONES)
       ========================================================================= */
    document.addEventListener('click', (e) => {
        const pageBtn = e.target.closest('.page-btn');
        if (!pageBtn || pageBtn.disabled || pageBtn.classList.contains('disabled')) return;

        const rawPage = pageBtn.dataset.page;
        if (!rawPage) return;

        const targetPage = parseInt(rawPage.trim(), 10);
        if (isNaN(targetPage) || targetPage < 1) return;

        e.preventDefault();
        e.stopImmediatePropagation();

        const inNotifications = pageBtn.closest('#latest-notifications-wrapper') ||
            pageBtn.closest('#js-pagination-notifications');

        if (inNotifications) {
            fetchNotifications(targetPage);
        } else {
            fetchEmployees(targetPage);
        }
    }, true);

    document.addEventListener('change', (e) => {
        if (!e.target.matches('.page-input')) return;

        const targetPage = parseInt(e.target.value.trim(), 10);
        if (isNaN(targetPage) || targetPage < 1) return;

        const inNotifications = e.target.closest('#latest-notifications-wrapper') ||
            e.target.closest('#js-pagination-notifications');

        if (inNotifications) {
            fetchNotifications(targetPage);
        } else {
            fetchEmployees(targetPage);
        }
    });

    document.addEventListener('keydown', (e) => {
        if (!e.target.matches('.page-input') || e.key !== 'Enter') return;
        e.preventDefault();
        e.target.dispatchEvent(new Event('change', {bubbles: true}));
    });

    /* =========================================================================
       6. MODALES Y EVENTOS AJAX
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

        const switchResponse = e.target.closest('.js-toggle-response');
        if (switchResponse && e.target.type === 'checkbox') {
            const notifId = switchResponse.dataset.id;
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
                        const textSpan = switchResponse.nextElementSibling?.querySelector('.switch-text');
                        if (textSpan) textSpan.textContent = data.label;
                    } else {
                        switchResponse.checked = !switchResponse.checked;
                    }
                })
                .catch(err => {
                    console.error('Error:', err);
                    switchResponse.checked = !switchResponse.checked;
                });
            return;
        }

        const btnArchive = e.target.closest('.js-btn-archive');
        if (btnArchive) {
            e.preventDefault();
            const notifId = btnArchive.dataset.id;

            Swal.fire({
                title: '¿Archivar trámite?',
                input: 'textarea',
                inputLabel: 'Motivo del archivado',
                inputPlaceholder: 'Ingrese las razones por las cuales se archiva este trámite...',
                showCancelButton: true,
                confirmButtonText: 'Archivar',
                cancelButtonText: 'Cancelar',
                customClass: {
                    confirmButton: 'swal2-confirm btn-swal-danger',
                    cancelButton: 'swal2-cancel btn-swal-cancel'
                },
                inputValidator: (value) => {
                    if (!value || !value.trim()) return 'Debe ingresar un motivo para archivar.';
                }
            }).then((result) => {
                if (result.isConfirmed) {
                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
                    const formData = new FormData();
                    formData.append('observation', result.value.trim());

                    fetch(`/sanctions/notifications/${notifId}/archive/`, {
                        method: 'POST',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': csrfToken
                        },
                        body: formData
                    })
                        .then(res => res.json())
                        .then(data => {
                            if (data.success) {
                                showToast(data.message || 'Trámite archivado con éxito.', 'success');
                                fetchNotifications(1);
                            } else {
                                Swal.fire('Error', data.message || 'No se pudo archivar.', 'error');
                            }
                        })
                        .catch(err => console.error('Error archivando:', err));
                }
            });
        }
    });

    document.addEventListener('submit', (e) => {
        const form = e.target;
        if (form.matches('#generateSanctionForm, #generateNotificationForm, #form-set-notified, #sanctionTypeForm, #assignNotificationForm, .ajax-sanction-form')) {
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