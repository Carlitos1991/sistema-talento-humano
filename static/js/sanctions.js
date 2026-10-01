/**
 * SIGETH - Módulo de Sanciones
 * Pestañas, búsqueda reactiva, selección masiva persistente, paginación y envío Ajax seguro.
 */
document.addEventListener('DOMContentLoaded', () => {

    const listUrl = window.location.pathname;
    let currentStatusFilter = 'all';
    let isSubmitting = false;

    // Detectar si estamos en la vista de historial de asignaciones
    const isHistoryView = window.location.pathname.includes('/history/');

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

    window.fetchEmployees = fetchEmployees;

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
       3. FILTROS, BÚSQUEDA Y STATS - NOTIFICACIONES / ASIGNACIONES
       ========================================================================= */
    const notifSearch = document.getElementById('notifications-search');
    const notifMonth = document.getElementById('notifications-month');
    const notifYear = document.getElementById('notifications-year');

    function fetchNotifications(page = 1) {
        const cleanPage = parseInt(String(page).trim(), 10) || 1;
        const params = new URLSearchParams();

        if (isHistoryView) {
            // SanctionHistoryListView usa 'page' normal
            params.set('page', cleanPage);
            if (currentStatusFilter && currentStatusFilter !== 'all') {
                params.set('status_filter', currentStatusFilter);
            }
            const q = notifSearch ? notifSearch.value.trim() : '';
            if (q) params.set('search_q', q);
            if (notifMonth && notifMonth.value) params.set('notifications_month', notifMonth.value);
            if (notifYear && notifYear.value) params.set('notifications_year', notifYear.value);
        } else {
            // EmployeeSanctionListView usa 'notifications_page'
            params.set('section', 'notifications');
            params.set('notifications_page', cleanPage);
            if (currentStatusFilter && currentStatusFilter !== 'all') {
                params.set('status_filter', currentStatusFilter);
            } else {
                params.set('status_filter', 'all');
            }
            const q = notifSearch ? notifSearch.value.trim() : '';
            if (q) params.set('notifications_q', q);
            if (notifMonth && notifMonth.value) params.set('notifications_month', notifMonth.value);
            if (notifYear && notifYear.value) params.set('notifications_year', notifYear.value);
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

    window.fetchNotifications = fetchNotifications;

    function updateStatsCards(statsList) {
        const statsContainer = document.querySelector('.stats-row');
        if (!statsContainer) return;

        statsContainer.innerHTML = '';
        statsList.forEach(stat => {
            const card = document.createElement('div');
            card.className = `stat-card ${stat.class || ''} js-notification-stat-filter`.trim();
            card.dataset.filterVal = stat.filter_val;
            card.style.cursor = 'pointer';

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
       4. CHECKBOXES PERSISTENTES Y ACCIONES MASIVAS
       ========================================================================= */
    const selectedNotificationIds = new Set();

    function updateBulkActionVisibility() {
        const bulkBar = document.getElementById('bulk-assign-actions');
        const countSpan = document.getElementById('selected-notifications-count');
        const masterCheck = document.getElementById('check-all-notifications');
        const currentCheckboxes = document.querySelectorAll('.js-notification-checkbox');

        // 1. Re-marcar checkboxes en la página actual según el Set
        currentCheckboxes.forEach(chk => {
            const id = String(chk.dataset.id || chk.value);
            chk.checked = selectedNotificationIds.has(id);
        });

        // 2. Estado del checkbox maestro
        if (masterCheck && currentCheckboxes.length > 0) {
            const totalInPage = currentCheckboxes.length;
            const checkedInPage = Array.from(currentCheckboxes).filter(chk => chk.checked).length;
            masterCheck.checked = (checkedInPage === totalInPage);
            masterCheck.indeterminate = (checkedInPage > 0 && checkedInPage < totalInPage);
        } else if (masterCheck) {
            masterCheck.checked = false;
            masterCheck.indeterminate = false;
        }

        // 3. Contadores y visibilidad
        const totalSelected = selectedNotificationIds.size;

        if (bulkBar) {
            if (totalSelected > 0) {
                bulkBar.classList.remove('hidden');
                if (countSpan) countSpan.textContent = `${totalSelected} seleccionado${totalSelected !== 1 ? 's' : ''}`;
            } else {
                bulkBar.classList.add('hidden');
            }
        }
    }

    document.addEventListener('change', (e) => {
        if (e.target && e.target.id === 'check-all-notifications') {
            const isChecked = e.target.checked;
            document.querySelectorAll('.js-notification-checkbox').forEach(chk => {
                const id = String(chk.dataset.id || chk.value);
                chk.checked = isChecked;
                if (isChecked) {
                    selectedNotificationIds.add(id);
                } else {
                    selectedNotificationIds.delete(id);
                }
            });
            updateBulkActionVisibility();
            return;
        }

        if (e.target && e.target.classList.contains('js-notification-checkbox')) {
            const id = String(e.target.dataset.id || e.target.value);
            if (e.target.checked) {
                selectedNotificationIds.add(id);
            } else {
                selectedNotificationIds.delete(id);
            }
            updateBulkActionVisibility();
        }
    });

    // Clic en Asignar Trámites Masivo
    document.addEventListener('click', (e) => {
        const btnBulk = e.target.closest('.js-btn-bulk-assign');
        if (!btnBulk) return;

        e.preventDefault();
        const allSelectedIds = Array.from(selectedNotificationIds);

        if (allSelectedIds.length === 0) {
            Swal.fire({
                icon: 'warning',
                title: 'Atención',
                text: 'Seleccione al menos una notificación para asignar.'
            });
            return;
        }

        const url = `/sanctions/notifications/assign/?ids=${allSelectedIds.join(',')}`;
        if (typeof window.openAjaxModal === 'function') {
            window.openAjaxModal(url);
        }
    });

    // Clic en Devolver Trámites Masivo
    document.addEventListener('click', (e) => {
        const btnReturn = e.target.closest('.js-btn-bulk-return');
        if (!btnReturn) return;

        e.preventDefault();
        const allSelectedIds = Array.from(selectedNotificationIds);

        if (allSelectedIds.length === 0) return;

        Swal.fire({
            title: `¿Devolver ${allSelectedIds.length} trámite(s)?`,
            text: 'Los trámites regresarán al estado inicial GENERADO.',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, devolver',
            cancelButtonText: 'Cancelar',
            customClass: {
                confirmButton: 'swal2-confirm btn-swal-danger',
                cancelButton: 'swal2-cancel btn-swal-cancel'
            }
        }).then(result => {
            if (result.isConfirmed) {
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
                const formData = new FormData();
                formData.append('notification_ids', allSelectedIds.join(','));

                fetch('/sanctions/notifications/massive-return/', {
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
                            if (typeof showToast === 'function') {
                                showToast(data.message || 'Trámite(s) devuelto(s) con éxito.', 'success');
                            }
                            selectedNotificationIds.clear();
                            fetchNotifications(1);
                        } else {
                            Swal.fire('Error', data.message || 'No se pudieron devolver los trámites.', 'error');
                        }
                    })
                    .catch(err => console.error('Error en devolución masiva:', err));
            }
        });
    });

    /* =========================================================================
       5. PAGINACIÓN ÚNICA (ADAPTABLE A CADA VISTA)
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

        if (isHistoryView) {
            fetchNotifications(targetPage);
        } else {
            const inNotifications = pageBtn.closest('#latest-notifications-wrapper') ||
                pageBtn.closest('#js-pagination-notifications');
            if (inNotifications) {
                fetchNotifications(targetPage);
            } else {
                fetchEmployees(targetPage);
            }
        }
    }, true);

    document.addEventListener('change', (e) => {
        if (!e.target.matches('.page-input')) return;

        const targetPage = parseInt(e.target.value.trim(), 10);
        if (isNaN(targetPage) || targetPage < 1) return;

        if (isHistoryView) {
            fetchNotifications(targetPage);
        } else {
            const inNotifications = e.target.closest('#latest-notifications-wrapper') ||
                e.target.closest('#js-pagination-notifications');
            if (inNotifications) {
                fetchNotifications(targetPage);
            } else {
                fetchEmployees(targetPage);
            }
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
                                if (typeof showToast === 'function') {
                                    showToast(data.message || 'Trámite archivado con éxito.', 'success');
                                }
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

    /* =========================================================================
       7. ENVÍO DE FORMULARIOS AJAX
       ========================================================================= */
    document.addEventListener('submit', (e) => {
        const form = e.target;
        if (!form.matches('#generateNotificationForm, #generateSanctionForm, #form-set-notified, #sanctionTypeForm, #assignNotificationForm, .ajax-sanction-form')) {
            return;
        }

        e.preventDefault();
        e.stopImmediatePropagation();

        if (isSubmitting) return;

        if (form.id === 'generateNotificationForm') {
            const notifTypeSelect = form.querySelector('[name="notification_type"]');
            const notifTypeValue = notifTypeSelect ? notifTypeSelect.value.trim() : '';

            if (!notifTypeValue) {
                Swal.fire({
                    icon: 'warning',
                    title: 'Campo Requerido',
                    text: 'Debe seleccionar el Tipo de Notificación antes de continuar.',
                    confirmButtonText: 'Entendido'
                });

                if (notifTypeSelect) {
                    notifTypeSelect.classList.add('is-invalid');
                    notifTypeSelect.scrollIntoView({behavior: 'smooth', block: 'center'});
                    notifTypeSelect.focus();
                }
                return;
            }
        }

        const submitBtn = form.querySelector('[type="submit"]');
        let originalBtnHtml = '';
        if (submitBtn) {
            originalBtnHtml = submitBtn.innerHTML;
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Guardando...';
        }

        isSubmitting = true;

        if (typeof window.submitAjaxForm === 'function') {
            window.submitAjaxForm(e, (data) => {
                isSubmitting = false;
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnHtml;
                }

                if (form.id === 'assignNotificationForm') {
                    selectedNotificationIds.clear();
                }

                if (isHistoryView) {
                    fetchNotifications(1);
                } else {
                    const activeTab = window.localStorage.getItem('sanctions-active-tab') || 'employees';
                    if (activeTab === 'notifications') {
                        fetchNotifications(1);
                    } else {
                        fetchEmployees(1);
                    }
                }
            });
        }

        setTimeout(() => {
            isSubmitting = false;
            if (submitBtn && submitBtn.disabled) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnHtml;
            }
        }, 1500);
    });

});