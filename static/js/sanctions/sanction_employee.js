document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const modalOverlay = document.getElementById('customModal');
    const modalContentContainer = document.getElementById('modal-dynamic-content');

    // Referencias de paginación
    const pageInfo = document.getElementById('page-info');
    const btnFirst = document.getElementById('btn-first');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const btnLast = document.getElementById('btn-last');
    const pageInput = document.getElementById('page-input');
    const currentPageDisplay = document.getElementById('current-page-display');
    const notificationsWrapper = document.getElementById('latest-notifications-wrapper');
    const notificationsMonthSelect = document.getElementById('notifications-month');
    const notificationsYearInput = document.getElementById('notifications-year');
    const tabButtons = document.querySelectorAll('.sanctions-tab-btn');
    const tabPanes = document.querySelectorAll('.sanctions-tab-pane');
    const notifSearchInput = document.getElementById('notifications-search');

    // Estado de paginación
    let currentPage = window.initialPagination ? window.initialPagination.current_page : 1;
    let totalPages = window.initialPagination ? window.initialPagination.total_pages : 1;
    let selectedNotificationIds = new Set();

    // Inicializar botones de paginación con datos del servidor
    if (window.initialPagination) {
        if (btnPrev) btnPrev.disabled = !window.initialPagination.has_previous;
        if (btnNext) btnNext.disabled = !window.initialPagination.has_next;
        if (btnFirst) btnFirst.disabled = !window.initialPagination.has_previous;
        if (btnLast) btnLast.disabled = !window.initialPagination.has_next;
    }
    if (notifSearchInput) {
        notifSearchInput.addEventListener('input', debounce(function () {
            fetchNotificationsPage(1);
        }, 500));
    }
    initTabs();

    // --- EVENTOS ---

    // 1. Buscador
    let timeout = null;
    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                currentPage = 1;
                fetchEmployeesPage(1, e.target.value);
            }, 300);
        });
    }

    // 2. Botones de paginación
    if (btnFirst) {
        btnFirst.addEventListener('click', () => {
            fetchEmployeesPage(1);
        });
    }

    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                fetchEmployeesPage(currentPage - 1);
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentPage < totalPages) {
                fetchEmployeesPage(currentPage + 1);
            }
        });
    }

    if (btnLast) {
        btnLast.addEventListener('click', () => {
            if (totalPages > 0) {
                fetchEmployeesPage(totalPages);
            }
        });
    }

    if (pageInput) {
        pageInput.addEventListener('change', () => {
            const targetPage = parseInt(pageInput.value, 10);
            if (!Number.isNaN(targetPage)) {
                fetchEmployeesPage(targetPage);
            }
        });
    }

    if (notificationsMonthSelect) {
        notificationsMonthSelect.addEventListener('change', () => fetchNotificationsPage(1));
    }

    if (notificationsYearInput) {
        notificationsYearInput.addEventListener('change', () => fetchNotificationsPage(1));
    }

    bindNotificationPagination();

    // 3. Cerrar Modal desde overlay o botón cerrar
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal')) {
                closeModal();
            }
        });
    }

    if (modalContentContainer) {
        modalContentContainer.addEventListener('click', function (e) {
            const listBtn = e.target.closest('.js-open-notification-list');
            if (listBtn) {
                e.preventDefault();
                openNotificationListModal(listBtn.dataset.url, listBtn.dataset.employeeId || '');
                return;
            }

            const editNotificationBtn = e.target.closest('.js-edit-notification');
            if (editNotificationBtn) {
                e.preventDefault();
                openGenerateNotificationModal(editNotificationBtn.dataset.employeeId, editNotificationBtn.dataset.notificationId || '');
                return;
            }
        });
    }

    bindNotificationEditButtons();

    // 5. DELEGACIÓN DE ACCIONES EN LA TABLA
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. GENERAR SANCIÓN
            const generateBtn = e.target.closest('.js-generate-sanction');
            if (generateBtn) {
                e.preventDefault();
                const employeeId = generateBtn.dataset.employeeId;
                openGenerateSanctionModal(employeeId);
                return;
            }

            // A2. GENERAR NOTIFICACIÓN
            const generateNotificationBtn = e.target.closest('.js-generate-notification');
            if (generateNotificationBtn) {
                e.preventDefault();
                const employeeId = generateNotificationBtn.dataset.employeeId;
                openGenerateNotificationModal(employeeId);
                return;
            }

            const notificationListBtn = e.target.closest('.js-open-notification-list');
            if (notificationListBtn) {
                e.preventDefault();
                openNotificationListModal(notificationListBtn.dataset.url, notificationListBtn.dataset.employeeId || '');
                return;
            }

            // B. VER HISTORIAL - Redirect to admin page filtered by employee
            const historyBtn = e.target.closest('.js-view-history');
            if (historyBtn) {
                e.preventDefault();
                const employeeId = historyBtn.dataset.employeeId;
                window.location.href = `/sanctions/admin/employee/${employeeId}/`;
                return;
            }
        });
    }

    // --- FUNCIONES ---

    function openGenerateSanctionModal(employeeId) {
        const url = `/sanctions/generate/?employee_id=${employeeId}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open');

                initModalPlugins();

                const form = modalContentContainer.querySelector('form');
                if (form) form.addEventListener('submit', handleSanctionFormSubmit);
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }

    function openGenerateNotificationModal(employeeId, notificationId = '') {
        const params = new URLSearchParams();
        if (employeeId) {
            params.set('employee_id', employeeId);
        }
        if (notificationId) {
            params.set('notification_id', notificationId);
        }
        const url = `/sanctions/notifications/generate/?${params.toString()}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open');

                initModalPlugins();

                const form = modalContentContainer.querySelector('#generateNotificationForm');
                if (form) form.addEventListener('submit', handleNotificationFormSubmit);
            })
            .catch(err => {
                console.error('Error al abrir modal de notificación:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario de notificación', 'error');
            });
    }

    function openNotificationListModal(url, employeeId = '') {
        const listUrl = employeeId ? `${url}?employee_id=${encodeURIComponent(employeeId)}` : url;

        fetch(listUrl, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open');

                initModalPlugins();
            })
            .catch(err => {
                console.error('Error al abrir listado de notificaciones:', err);
                Swal.fire('Error', 'No se pudo cargar el listado de notificaciones', 'error');
            });
    }


    function closeModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
        document.body.classList.remove('modal-open');
    }

    function initModalPlugins() {
        // Inicializar Select2
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                width: '100%', dropdownParent: modalOverlay
            });
        }

        // Initialize custom accordion
        const accordionToggles = document.querySelectorAll('.accordion-toggle');
        accordionToggles.forEach(toggle => {
            toggle.addEventListener('click', function () {
                const targetId = this.getAttribute('data-target');
                const content = document.getElementById(targetId);

                if (content) {
                    const isOpen = content.style.display === 'block';

                    if (isOpen) {
                        content.style.display = 'none';
                        content.classList.remove('show');
                        this.classList.add('collapsed');
                    } else {
                        content.style.display = 'block';
                        content.classList.add('show');
                        this.classList.remove('collapsed');
                    }
                }
            });
        });
    }

    function initPersistentSelectAll() {
        const masterCheck = document.getElementById('check-all-notifications');
        const itemChecks = document.querySelectorAll('.js-notification-checkbox');

        if (!masterCheck) return;

        // 1. Sincronizar estado visual con el Set global
        itemChecks.forEach(cb => {
            if (selectedNotificationIds.has(cb.dataset.id)) {
                cb.checked = true;
            }
        });

        // 2. Actualizar el estado del Master Check (indeterminado o marcado)
        updateMasterCheckState(masterCheck, itemChecks);

        // 3. Evento para el Master Check
        // Usamos onclick para asegurar que solo haya un listener activo si se re-llama
        masterCheck.onchange = function () {
            itemChecks.forEach(cb => {
                cb.checked = this.checked;
                const id = cb.dataset.id;
                if (this.checked) {
                    selectedNotificationIds.add(id);
                } else {
                    selectedNotificationIds.delete(id);
                }
            });
        };

        // 4. Eventos para checks individuales
        itemChecks.forEach(cb => {
            cb.onchange = function () {
                const id = this.dataset.id;
                if (this.checked) {
                    selectedNotificationIds.add(id);
                } else {
                    selectedNotificationIds.delete(id);
                }
                updateMasterCheckState(masterCheck, itemChecks);
            };
        });
    }

    function updateMasterCheckState(masterCheck, itemChecks) {
        if (itemChecks.length === 0) {
            masterCheck.checked = false;
            masterCheck.indeterminate = false;
            return;
        }

        const checkedInPage = Array.from(itemChecks).filter(cb => cb.checked).length;

        masterCheck.checked = (checkedInPage === itemChecks.length);
        masterCheck.indeterminate = (checkedInPage > 0 && checkedInPage < itemChecks.length);
    }

    function handleSanctionFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

        fetch(form.action, {
            method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async res => {
                const contentType = res.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    throw new Error('Respuesta no válida del servidor');
                }

                const data = await res.json();

                if (res.ok) {
                    closeModal();
                    const Toast = Swal.mixin({
                        toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true
                    });
                    Toast.fire({
                        icon: 'success', title: data.message || 'Sanción registrada correctamente'
                    });
                } else {
                    if (res.status === 403) {
                        Swal.fire('Acceso denegado', data.message || 'No tiene permisos para realizar esta acción', 'error');
                    } else if (data.errors) {
                        showErrors(form, data.errors);
                    } else {
                        Swal.fire('Error', data.message || 'Ocurrió un error al guardar', 'error');
                    }
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }

    function handleNotificationFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

        fetch(form.action, {
            method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async res => {
                const data = await res.json().catch(() => ({}));

                if (res.ok && data.success) {
                    closeModal();
                    const Toast = Swal.mixin({
                        toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true
                    });
                    Toast.fire({icon: 'success', title: data.message || 'Notificación generada correctamente'});

                    const activeTab = getActiveTab();
                    if (activeTab === 'notifications') {
                        // Refresh notifications page
                        const currentNotificationsPage = parseInt(document.getElementById('notifications-page-input')?.value) || 1;
                        fetchNotificationsPage(currentNotificationsPage);
                        return;
                    }

                    const searchQuery = searchInput ? searchInput.value : '';
                    fetchEmployeesPage(currentPage, searchQuery);
                    return;
                }

                if (res.status === 403) {
                    Swal.fire('Acceso denegado', data.message || 'No tiene permisos para realizar esta acción', 'error');
                } else if (data.errors) {
                    showErrors(form, data.errors);
                } else {
                    Swal.fire('Error', data.message || 'Ocurrió un error al generar la notificación', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }


    function fetchEmployeesPage(page, searchQuery = null) {
        const query = searchQuery !== null ? searchQuery : (searchInput ? searchInput.value : '');
        const params = new URLSearchParams();
        params.set('page', page);
        if (query) {
            params.set('q', query);
        }

        fetch(`${urlList}?${params.toString()}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                if (tableContainer && data.html) {
                    tableContainer.innerHTML = data.html;
                    if (data.pagination) {
                        updatePagination(data.pagination);
                    }
                }
            })
            .catch(err => console.error('Error al cargar empleados:', err));
    }

    function fetchNotificationsPage(page) {
        const params = new URLSearchParams();
        params.set('section', 'notifications');
        params.set('notifications_page', page);

        // Agregamos el filtro de búsqueda COD/EMP
        const q = document.getElementById('notifications-search')?.value;
        if (q) params.set('notifications_q', q);

        if (notificationsMonthSelect && notificationsMonthSelect.value) {
            params.set('notifications_month', notificationsMonthSelect.value);
        }
        if (notificationsYearInput && notificationsYearInput.value) {
            params.set('notifications_year', notificationsYearInput.value);
        }
        fetch(`${urlList}?${params.toString()}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                if (notificationsWrapper && data.html) {
                    notificationsWrapper.innerHTML = data.html;
                    bindNotificationEditButtons();
                    bindNotificationPagination();
                    initPersistentSelectAll();
                }
            })
            .catch(err => console.error('Error al cargar notificaciones:', err));
    }

    function initTabs() {
        if (!tabButtons.length || !tabPanes.length) {
            return;
        }

        const storedTab = window.localStorage.getItem('sanctions-list-tab');
        const initialTab = storedTab && document.querySelector(`[data-sanctions-tab="${storedTab}"]`) ? storedTab : 'employees';
        setActiveTab(initialTab, false);

        tabButtons.forEach((button) => {
            button.addEventListener('click', () => {
                setActiveTab(button.dataset.sanctionsTab, true);
            });
        });
    }

    function setActiveTab(tabName, persist = true) {
        tabButtons.forEach((button) => {
            const isActive = button.dataset.sanctionsTab === tabName;
            button.classList.toggle('is-active', isActive);
            button.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        tabPanes.forEach((pane) => {
            const isActive = pane.dataset.sanctionsPane === tabName;
            pane.classList.toggle('is-active', isActive);
            pane.hidden = !isActive;
        });
        if (tabName === 'notifications') {
            initPersistentSelectAll();
        }
        if (persist) {
            window.localStorage.setItem('sanctions-list-tab', tabName);
        }
    }

    function getActiveTab() {
        const activeButton = document.querySelector('.sanctions-tab-btn.is-active');
        return activeButton ? activeButton.dataset.sanctionsTab : 'employees';
    }

    function bindNotificationEditButtons() {
        // Enlazar botones de editar notificacion desde la tabla de historial de notificaciones
        document.querySelectorAll('.js-edit-notification').forEach((button) => {
            if (button.dataset.bound === '1') {
                return;
            }

            button.addEventListener('click', (event) => {
                event.preventDefault();
                openGenerateNotificationModal(button.dataset.employeeId || '', button.dataset.notificationId || '');
            });

            button.dataset.bound = '1';
        });
    }

    function bindNotificationPagination() {
        const notificationsFirst = document.getElementById('notifications-btn-first');
        const notificationsPrev = document.getElementById('notifications-btn-prev');
        const notificationsNext = document.getElementById('notifications-btn-next');
        const notificationsLast = document.getElementById('notifications-btn-last');
        const notificationsPageInput = document.getElementById('notifications-page-input');

        if (notificationsFirst && notificationsFirst.dataset.bound !== '1') {
            notificationsFirst.addEventListener('click', () => fetchNotificationsPage(1));
            notificationsFirst.dataset.bound = '1';
        }

        if (notificationsPrev && notificationsPrev.dataset.bound !== '1') {
            notificationsPrev.addEventListener('click', () => {
                const current = parseInt(notificationsPageInput ? notificationsPageInput.value : '1', 10) || 1;
                if (current > 1) {
                    fetchNotificationsPage(current - 1);
                }
            });
            notificationsPrev.dataset.bound = '1';
        }

        if (notificationsNext && notificationsNext.dataset.bound !== '1') {
            notificationsNext.addEventListener('click', () => {
                const current = parseInt(notificationsPageInput ? notificationsPageInput.value : '1', 10) || 1;
                const total = parseInt(notificationsPageInput ? notificationsPageInput.max : '1', 10) || 1;
                if (current < total) {
                    fetchNotificationsPage(current + 1);
                }
            });
            notificationsNext.dataset.bound = '1';
        }

        if (notificationsLast && notificationsLast.dataset.bound !== '1') {
            notificationsLast.addEventListener('click', () => {
                const total = parseInt(notificationsPageInput ? notificationsPageInput.max : '1', 10) || 1;
                fetchNotificationsPage(total);
            });
            notificationsLast.dataset.bound = '1';
        }

        if (notificationsPageInput && notificationsPageInput.dataset.bound !== '1') {
            notificationsPageInput.addEventListener('change', () => {
                const targetPage = parseInt(notificationsPageInput.value, 10);
                const total = parseInt(notificationsPageInput.max, 10) || 1;
                if (!Number.isNaN(targetPage)) {
                    const safePage = Math.min(Math.max(targetPage, 1), total);
                    fetchNotificationsPage(safePage);
                }
            });
            notificationsPageInput.dataset.bound = '1';
        }
    }

    function updatePagination(paginationData) {
        currentPage = paginationData.current_page;
        totalPages = paginationData.total_pages;

        if (pageInfo) {
            pageInfo.textContent = `Mostrando ${paginationData.start_index} a ${paginationData.end_index} registros de ${paginationData.total_count} registros`;
        }

        if (currentPageDisplay) {
            currentPageDisplay.textContent = currentPage;
        }

        if (btnFirst) btnFirst.disabled = !paginationData.has_previous;
        if (btnPrev) btnPrev.disabled = !paginationData.has_previous;
        if (btnNext) btnNext.disabled = !paginationData.has_next;
        if (btnLast) btnLast.disabled = !paginationData.has_next;

        if (pageInput) {
            pageInput.value = currentPage;
            pageInput.max = totalPages;
        }
    }

    function showErrors(form, errors) {
        for (const [field, msgs] of Object.entries(errors)) {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('is-invalid');
                const feedback = input.parentNode.querySelector('.invalid-feedback');
                if (feedback) feedback.textContent = Array.isArray(msgs) ? msgs.join(', ') : msgs;
            }
        }
    }

    document.addEventListener('click', function (e) {
        const toggle = e.target.closest('.js-toggle-response');
        if (toggle) {
            const notificationId = toggle.dataset.id;
            const csrf = document.getElementById('csrf-token').value;

            // Cambiamos la URL para que use el nombre de la app si es necesario
            fetch(`/sanctions/notifications/${notificationId}/toggle-response/`, {
                method: 'POST', headers: {
                    'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const textSpan = toggle.querySelector('.modern-toggle-text');
                        textSpan.textContent = data.label;

                        if (data.has_responded) {
                            toggle.classList.add('modern-toggle-green');
                        } else {
                            toggle.classList.remove('modern-toggle-green');
                        }
                    }
                })
                .catch(error => console.error('Error:', error));
        }
    });

    function debounce(func, wait) {
        let timeout;
        return function () {
            const context = this, args = arguments;
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(context, args), wait);
        };
    }
});