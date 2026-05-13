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
    const btnBulkAssign = document.getElementById('btn-bulk-assign');
    // Estado de paginación
    let currentPage = window.initialPagination ? window.initialPagination.current_page : 1;
    let totalPages = window.initialPagination ? window.initialPagination.total_pages : 1;
    let selectedNotificationIds = new Set();

    // Inicializar botones de paginación con datos del servidor
    if (window.initialPagination) {
        const btn1st = document.getElementById('btn-first');
        const btnP = document.getElementById('btn-prev');
        const btnN = document.getElementById('btn-next');
        const btnL = document.getElementById('btn-last');

        if (btnP) btnP.disabled = !window.initialPagination.has_previous;
        if (btnN) btnN.disabled = !window.initialPagination.has_next;
        if (btn1st) btn1st.disabled = !window.initialPagination.has_previous;
        if (btnL) btnL.disabled = !window.initialPagination.has_next;
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
    bindEmployeePagination();

    function bindEmployeePagination() {
        // Reasignar referencias después de cada AJAX
        const btn1st = document.getElementById('btn-first');
        const btnP = document.getElementById('btn-prev');
        const btnN = document.getElementById('btn-next');
        const btnL = document.getElementById('btn-last');
        const pageInp = document.getElementById('page-input');

        if (!btn1st && !btnP && !btnN && !btnL) {
            // Si no encontramos los botones, salimos
            return;
        }

        if (btn1st) {
            btn1st.onclick = () => {
                currentPage = 1;
                fetchEmployeesPage(1);
            };
        }

        if (btnP) {
            btnP.onclick = () => {
                if (currentPage > 1) {
                    fetchEmployeesPage(currentPage - 1);
                }
            };
        }

        if (btnN) {
            btnN.onclick = () => {
                if (currentPage < totalPages) {
                    fetchEmployeesPage(currentPage + 1);
                }
            };
        }

        if (btnL) {
            btnL.onclick = () => {
                if (totalPages > 0) {
                    fetchEmployeesPage(totalPages);
                }
            };
        }

        if (pageInp) {
            pageInp.onchange = () => {
                const targetPage = parseInt(pageInp.value, 10);
                if (!Number.isNaN(targetPage) && targetPage >= 1 && targetPage <= totalPages) {
                    currentPage = targetPage;
                    fetchEmployeesPage(targetPage);
                }
            };
        }
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

        modalContentContainer.addEventListener('change', function (e) {
            const fileInput = e.target.closest('.file-input');
            if (!fileInput) {
                return;
            }

            const wrapper = fileInput.closest('.custom-file-upload');
            const fileNameSpan = wrapper ? wrapper.querySelector('.file-name') : null;
            if (fileNameSpan) {
                fileNameSpan.textContent = fileInput.files.length > 0
                    ? fileInput.files[0].name
                    : 'Ningún archivo seleccionado';
            }
        });

        modalContentContainer.addEventListener('submit', function (e) {
            const sanctionForm = e.target.closest('#generateSanctionForm');
            if (sanctionForm) {
                handleSanctionFormSubmit(e);
                return;
            }

            const editForm = e.target.closest('#editPersonnelActionForm');
            if (editForm) {
                handleEditPersonnelActionFormSubmit(e);
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

    // Delegación para el botón de asignar
    if (notificationsWrapper) {
        notificationsWrapper.addEventListener('click', function (e) {
            // Detectar clic en el botón con la clase js-assign-notification
            const assignBtn = e.target.closest('.js-assign-notification');
            if (assignBtn) {
                e.preventDefault();
                const notifId = assignBtn.dataset.id;
                openAssignModal(notifId);
            }

            // Detectar clic en el botón de editar PersonnelAction
            const editActionBtn = e.target.closest('.js-btn-edit-personnel-action');
            if (editActionBtn) {
                e.preventDefault();
                const actionId = editActionBtn.dataset.actionId;
                openEditPersonnelActionModal(actionId);
            }

            // Detectar clic en el botón de ver ruta del trámite
            const routeBtn = e.target.closest('.js-btn-route-tramite');
            if (routeBtn) {
                e.preventDefault();
                openRouteTramiteModal(routeBtn.dataset.notificationId);
            }
        });
    }

    function toggleBulkAssignButton() {
        if (!btnBulkAssign) return;

        if (selectedNotificationIds.size > 0) {
            // Mostrar botón y actualizar contador
            btnBulkAssign.style.display = 'inline-flex';
            btnBulkAssign.innerHTML = `<i class="fa-solid fa-arrow-right-to-bracket"></i> Asignar (${selectedNotificationIds.size})`;
        } else {
            // Ocultar si no hay nada seleccionado
            btnBulkAssign.style.display = 'none';
        }
    }

    function openAssignModal(ids) {
        // Cargamos el modal (puedes usar la misma vista AssignNotificationAjaxView que creamos antes)
        fetch(`/sanctions/notifications/assign/?ids=${ids}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open');

                // --- CONFIGURAR SELECT2 AJAX DENTRO DEL MODAL ---
                const $select = $('#select-responsible-ajax');
                if ($select.length) {
                    $select.select2({
                        dropdownParent: $('#customModal'), // Importante para que se vea sobre el modal
                        placeholder: 'Buscar por cédula o nombre...',
                        minimumInputLength: 3,
                        ajax: {
                            url: '/sanctions/users/search/', // La URL de la vista del paso 2
                            dataType: 'json',
                            delay: 250,
                            data: function (params) {
                                return {q: params.term};
                            },
                            processResults: function (data) {
                                return {results: data.results};
                            },
                            cache: true
                        }
                    });
                }

                // --- MANEJAR EL ENVÍO DEL FORMULARIO ---
                const form = document.getElementById('assignNotificationForm');
                if (form) {
                    form.addEventListener('submit', function (e) {
                        e.preventDefault();
                        const formData = new FormData(this);

                        fetch(this.action, {
                            method: 'POST',
                            body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        })
                            .then(res => res.json())
                            .then(data => {
                                if (data.success) {

                                    Swal.fire('¡Éxito!', data.message, 'success');
                                    closeModal();
                                    selectedNotificationIds.clear(); // Limpiamos la selección
                                    fetchNotificationsPage(1); // Refrescamos la tabla
                                } else {
                                    Swal.fire('Error', data.message, 'error');
                                }
                            });
                    });
                }
            });
    }

    // --- FUNCIONES ---
    function toggleBulkButton() {
        if (btnBulkAssign) {
            btnBulkAssign.addEventListener('click', function () {
                // Verificamos si hay elementos seleccionados en el Set global
                if (selectedNotificationIds.size === 0) {
                    Swal.fire({
                        icon: 'warning',
                        title: 'Sin selección',
                        text: 'Por favor, seleccione al menos una notificación de la lista.',
                        confirmButtonColor: '#3b82f6'
                    });
                    return;
                }
                const ids = Array.from(selectedNotificationIds).join(',');
                openAssignModal(ids);
            });
        }
    }

    function openGenerateSanctionModal(employeeId, notificationId = null) {
        let url = `/sanctions/generate/?employee_id=${employeeId}`;
        if (notificationId) url += `&notification_id=${notificationId}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;

                // 1. Mostrar el modal antes de inicializar nada
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open');

                // 2. Usar un tiempo de espera un poco mayor para asegurar el renderizado
                setTimeout(() => {
                    // Destruir instancias previas si existen para evitar errores
                    if ($('.js-authority-ajax').data('select2')) {
                        $('.js-authority-ajax').select2('destroy');
                    }

                    $('.js-authority-ajax').select2({
                        dropdownParent: $('#customModal'),
                        placeholder: 'Buscar por nombre o cédula...',
                        minimumInputLength: 2,
                        width: '100%',
                        ajax: {
                            url: '/sanctions/users/search/',
                            dataType: 'json',
                            delay: 250,
                            data: params => ({q: params.term}),
                            processResults: data => ({results: data.results}),
                            cache: true
                        }
                    });

                    initModalPlugins();
                }, 300); // 300ms es más seguro
            });
    }

    function openEditPersonnelActionModal(actionId) {
        const url = `/sanctions/personnel-action/${actionId}/edit/`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;

                // Mostrar el modal
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open');

                // Inicializar componentes
                setTimeout(() => {
                    initModalPlugins();
                }, 300);
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

    function openRouteTramiteModal(notificationId) {
        if (!notificationId) {
            console.error('notificationId es requerido');
            return;
        }

        fetch(`/sanctions/notifications/${notificationId}/route/`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open');
            })
            .catch(err => {
                console.error('Error al abrir ruta del trámite:', err);
                Swal.fire('Error', 'No se pudo cargar la ruta del trámite', 'error');
            });
    }

    function closeModal() {
        $('#customModal').addClass('hidden');
        $('#modal-dynamic-content').html('');
        $('body').removeClass('modal-open');
    }

    function initModalPlugins() {
        // Inicializar Select2
        if (typeof $ !== 'undefined' && $.fn.select2) {
            const $responsibleSelect = $('#select-responsible-ajax');
            if ($responsibleSelect.length) {
                $responsibleSelect.select2({
                    dropdownParent: $('#customModal'),
                    placeholder: 'Buscar responsable...',
                    minimumInputLength: 2,
                    width: '100%',
                    ajax: {
                        url: '/sanctions/users/search/',
                        dataType: 'json',
                        delay: 250,
                        data: params => ({q: params.term}),
                        processResults: data => ({results: data.results}),
                        cache: true
                    }
                });
            }

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

        // Initialize file input handlers
        const fileInputs = document.querySelectorAll('.file-input');
        fileInputs.forEach(input => {
            input.addEventListener('change', function (e) {
                const wrapper = this.closest('.custom-file-upload');
                const fileLabel = wrapper?.querySelector('.file-name');
                const fileText = wrapper?.querySelector('.file-text');
                const fileIcon = wrapper?.querySelector('.file-icon');
                if (wrapper) {
                    wrapper.classList.toggle('has-file', this.files.length > 0);
                }
                if (fileIcon) {
                    fileIcon.className = this.files.length > 0
                        ? 'fas fa-file-pdf file-icon'
                        : 'fas fa-cloud-upload-alt file-icon';
                }
                if (fileLabel) {
                    fileLabel.textContent = this.files.length > 0 ? this.files[0].name : 'Ningún archivo seleccionado';
                }
                if (fileText) {
                    fileText.textContent = this.files.length > 0 ? 'Archivo seleccionado' : 'Seleccionar archivo';
                }
            });
        });
    }

    function initPersistentSelectAll() {
        const masterCheck = document.getElementById('check-all-notifications');
        const itemChecks = document.querySelectorAll('.js-notification-checkbox');

        if (!masterCheck) return;

        // Sincronizar estado visual al cargar página/pestaña
        itemChecks.forEach(cb => {
            if (selectedNotificationIds.has(cb.dataset.id)) {
                cb.checked = true;
            }
        });

        updateMasterCheckState(masterCheck, itemChecks);
        toggleBulkAssignButton();

        // Evento Master Check
        masterCheck.onchange = function () {
            itemChecks.forEach(cb => {
                cb.checked = this.checked;
                const id = cb.dataset.id;
                if (this.checked) {
                    selectedNotificationIds.add(id);
                } else {
                    selectedNotificationIds.delete(id);
                    openAssignModal
                }
            });
            toggleBulkAssignButton();
        };

        // Eventos Checks Individuales
        itemChecks.forEach(cb => {
            cb.onchange = function () {
                const id = this.dataset.id;
                if (this.checked) {
                    selectedNotificationIds.add(id);
                } else {
                    selectedNotificationIds.delete(id);
                }
                updateMasterCheckState(masterCheck, itemChecks);
                toggleBulkAssignButton();
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

        toggleBulkButton();
    }

    if (btnBulkAssign) {
        btnBulkAssign.addEventListener('click', function () {
            if (selectedNotificationIds.size > 0) {
                const ids = Array.from(selectedNotificationIds).join(',');
                openAssignModal(ids);
            }
        });
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

                    // Recargar la tabla y estadísticas
                    const activeTab = getActiveTab();
                    if (activeTab === 'notifications') {
                        const currentPage = parseInt(document.getElementById('notifications-page-input')?.value) || 1;
                        fetchNotificationsPage(currentPage);
                    } else {
                        const searchQuery = searchInput ? searchInput.value : '';
                        fetchEmployeesPage(currentPage, searchQuery);
                    }
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

    function handleEditPersonnelActionFormSubmit(e) {
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
                        icon: 'success', title: data.message || 'Acción de Personal actualizada correctamente'
                    });
                    // Recargar la tabla de notificaciones
                    const activeTab = getActiveTab();
                    if (activeTab === 'notifications') {
                        const currentPage = parseInt(document.getElementById('notifications-page-input')?.value) || 1;
                        fetchNotificationsPage(currentPage);
                    }
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
                    bindEmployeePagination();
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

        // Agregar status_filter (default 'all' si no está presente)
        const urlParams = new URLSearchParams(window.location.search);
        const currentStatus = urlParams.get('status_filter') || 'all';
        params.set('status_filter', currentStatus);

        fetch(`${urlList}?${params.toString()}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                if (notificationsWrapper && data.html) {
                    notificationsWrapper.innerHTML = data.html;
                    bindNotificationEditButtons();
                    bindNotificationPagination();
                    initPersistentSelectAll();
                    updateNotificationsPaginationInfo(data.pagination);
                    // Actualizar stats de notificaciones
                    if (data.stats && data.stats.length > 0) {
                        updateNotificationsStats(data.stats);
                    }
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
        } else {
            if (btnBulkAssign) btnBulkAssign.style.display = 'none';
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

    function updateNotificationsStats(statsData) {
        const statsRow = document.querySelector('[data-sanctions-pane="notifications"] .stats-row');
        if (!statsRow) return;

        // Reconstruir stats cards
        statsRow.innerHTML = '';
        statsData.forEach(stat => {
            const statCard = document.createElement('div');
            statCard.className = `stat-card ${stat.class}`;
            statCard.onclick = function () {
                filterNotificationsByStatus(stat.filter_val);
            };
            statCard.innerHTML = `
                <div class="stat-left">
                    <h3>${stat.label}</h3>
                    <div class="number">${stat.count}</div>
                </div>
                <i class="fas ${stat.icon} stat-icon"></i>
            `;
            statsRow.appendChild(statCard);
        });
    }

    function updatePagination(paginationData) {
        currentPage = paginationData.current_page;
        totalPages = paginationData.total_pages;

        // Buscar los elementos nuevamente por si se actualizaron
        const pageInfoElement = document.getElementById('page-info');
        const pageInputElement = document.getElementById('page-input');
        const btnFirstElement = document.getElementById('btn-first');
        const btnPrevElement = document.getElementById('btn-prev');
        const btnNextElement = document.getElementById('btn-next');
        const btnLastElement = document.getElementById('btn-last');

        if (pageInfoElement) {
            pageInfoElement.textContent = `Mostrando ${paginationData.start_index} a ${paginationData.end_index} de ${paginationData.total_count}`;
        }

        if (btnFirstElement) btnFirstElement.disabled = !paginationData.has_previous;
        if (btnPrevElement) btnPrevElement.disabled = !paginationData.has_previous;
        if (btnNextElement) btnNextElement.disabled = !paginationData.has_next;
        if (btnLastElement) btnLastElement.disabled = !paginationData.has_next;

        if (pageInputElement) {
            pageInputElement.value = currentPage;
            pageInputElement.max = totalPages;
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

    $(document).on('click', '.js-btn-set-notified', function () {
        const url = $(this).data('url');
        fetch(url)
            .then(response => response.text())
            .then(html => {
                $('#modal-dynamic-content').html(html);
                $('#customModal').removeClass('hidden');
                $('body').addClass('modal-open'); // Bloquea el scroll
            });
    });

    $(document).on('submit', '#form-set-notified', function (e) {
        e.preventDefault();
        const $form = $(this);
        $.ajax({
            url: $form.attr('data-url'),
            method: 'POST',
            data: $form.serialize(),
            success: function (response) {
                if (response.success) {
                    closeModal();
                    Swal.fire('¡Éxito!', response.message, 'success');

                    // IMPORTANTE: Recargar la página 1 de notificaciones
                    // Esto actualiza la tabla Y los stats (contadores superiores)
                    fetchNotificationsPage(1);
                }
            },
            error: function (err) {
                Swal.fire('Error', 'No se pudo guardar la fecha', 'error');
            }
        });
    });

    // Función para abrir el modal (donde haces el fetch del botón verde)
    function openNotificationModal(url) {
        fetch(url)
            .then(response => response.text())
            .then(html => {
                $('#modal-dynamic-content').html(html);
                $('#customModal').removeClass('hidden');
                $('body').addClass('modal-open'); // <--- BLOQUEA EL SCROLL
            });
    }

// Función para cerrar el modal (closeModal)
    function closeModal() {
        $('#customModal').addClass('hidden');
        $('#modal-dynamic-content').html('');
        $('body').removeClass('modal-open'); // <--- ACTIVA EL SCROLL DE NUEVO
    }

    // --- FUNCIÓN PARA FILTRAR NOTIFICACIONES POR ESTADO ---
    window.filterNotificationsByStatus = function (status) {
        const month = document.getElementById('notifications-month').value;
        const year = document.getElementById('notifications-year').value;
        const q = document.getElementById('notifications-search').value;

        let url = `${urlList}?page=1&section=notifications`;

        // Agregar status_filter siempre (incluso 'all' para mostrar todos)
        url += `&status_filter=${status}`;

        if (month) url += `&notifications_month=${month}`;
        if (year) url += `&notifications_year=${year}`;
        if (q) url += `&notifications_q=${encodeURIComponent(q)}`;

        // Actualizar URL del navegador
        window.history.replaceState({}, '', url);

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (notificationsWrapper && data.html) {
                    notificationsWrapper.innerHTML = data.html;
                    bindNotificationEditButtons();
                    bindNotificationPagination();
                    initPersistentSelectAll();
                    updateNotificationsPaginationInfo(data.pagination);
                    // Actualizar stats de notificaciones
                    if (data.stats && data.stats.length > 0) {
                        updateNotificationsStats(data.stats);
                    }
                }
            })
            .catch(() => Swal.fire({icon: 'error', title: 'Error de conexión'}));
    };

    // --- FUNCIÓN PARA ACTUALIZAR INFO DE PAGINACIÓN DE NOTIFICACIONES ---
    function updateNotificationsPaginationInfo(paginationData) {
        const pageInfo = document.getElementById('notifications-page-info');
        const pageInput = document.getElementById('notifications-page-input');

        if (pageInfo && paginationData) {
            pageInfo.textContent = `Mostrando ${paginationData.start_index} a ${paginationData.end_index} de ${paginationData.total_count}`;
        }

        if (pageInput && paginationData) {
            pageInput.max = paginationData.total_pages;
            pageInput.value = paginationData.current_page;
        }

        // Actualizar estado de botones
        const btnFirst = document.getElementById('notifications-btn-first');
        const btnPrev = document.getElementById('notifications-btn-prev');
        const btnNext = document.getElementById('notifications-btn-next');
        const btnLast = document.getElementById('notifications-btn-last');

        if (btnFirst) btnFirst.disabled = !paginationData.has_previous;
        if (btnPrev) btnPrev.disabled = !paginationData.has_previous;
        if (btnNext) btnNext.disabled = !paginationData.has_next;
        if (btnLast) btnLast.disabled = !paginationData.has_next;
    }
});