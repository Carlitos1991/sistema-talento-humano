document.addEventListener('DOMContentLoaded', function () {
    const urlList = document.getElementById('url-list').value;
    const notificationsWrapper = document.getElementById('latest-notifications-wrapper');
    const customModal = document.getElementById('customModal');
    const modalContent = document.getElementById('modal-dynamic-content');
    const selectedIds = new Set();

    // Botones Masivos de la cabecera
    const massiveAssignBtn = document.getElementById('btn-massive-assign');
    const massiveReturnBtn = document.getElementById('btn-massive-return');
    const countAssign = document.getElementById('count-assign');
    const countReturn = document.getElementById('count-return');

    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 2000,
        timerProgressBar: true
    });

    // --- 1. LÓGICA PARA CERRAR EL MODAL ---
    document.addEventListener('click', function (e) {
        if (e.target.closest('.js-close-modal') || e.target === customModal) {
            customModal.classList.add('hidden');
            modalContent.innerHTML = '';
        }
    });

    function updateMassiveButtons() {
        const size = selectedIds.size;
        if (size > 0) {
            massiveAssignBtn.classList.remove('hidden');
            massiveReturnBtn.classList.remove('hidden');
            if (countAssign) countAssign.textContent = size;
            if (countReturn) countReturn.textContent = size;
        } else {
            massiveAssignBtn.classList.add('hidden');
            massiveReturnBtn.classList.add('hidden');
        }
    }

    function bindEvents() {
        // Paginador
        const pageInput = document.getElementById('notifications-page-input');
        if (pageInput) {
            pageInput.addEventListener('change', function () {
                fetchHistoryPage(parseInt(this.value) || 1);
            });
        }

        // Checkboxes
        const checkboxes = document.querySelectorAll('.js-notification-checkbox');
        const checkAll = document.getElementById('check-all-notifications');

        if (checkAll) {
            checkAll.onclick = function () {
                checkboxes.forEach(cb => {
                    cb.checked = this.checked;
                    this.checked ? selectedIds.add(cb.value) : selectedIds.delete(cb.value);
                });
                updateMassiveButtons();
            };
        }

        checkboxes.forEach(cb => {
            cb.onclick = function () {
                this.checked ? selectedIds.add(this.value) : selectedIds.delete(this.value);
                updateMassiveButtons();
            };
        });
        // 1. ACCIÓN: ARCHIVAR
        document.querySelectorAll('.js-btn-archive').forEach(btn => {
            btn.onclick = () => {
                Swal.fire({
                    title: 'Archivar Notificación',
                    text: 'Escriba el motivo del archivo:',
                    input: 'textarea',
                    inputPlaceholder: 'Ej: El empleado justificó el atraso...',
                    inputAttributes: {'aria-label': 'Escriba el motivo'},
                    showCancelButton: true,
                    confirmButtonText: 'Archivar Trámite',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: '#64748b',
                    inputValidator: (value) => {
                        if (!value) return '¡Debe escribir un motivo!'
                    }
                }).then((result) => {
                    if (result.isConfirmed) {
                        const formData = new FormData();
                        formData.append('observation', result.value);
                        executeAction(`/sanctions/notifications/${btn.dataset.id}/archive/`, formData);
                    }
                });
            };
        });

        function openGenerateSanctionModal(employeeId, notificationId = null) {
            // 1. Cargamos el modal de sanción normal
            fetch(`/sanctions/generate/?employee_id=${employeeId}`)
                .then(res => res.text())
                .then(html => {
                    const modalContent = document.getElementById('modal-dynamic-content');
                    modalContent.innerHTML = html;

                    // 2. Si venimos desde el historial, metemos el notificationId oculto en el FORM
                    if (notificationId) {
                        const form = modalContent.querySelector('form'); // El form de sanción
                        if (form) {
                            const input = document.createElement('input');
                            input.type = 'hidden';
                            input.name = 'notification_id';
                            input.value = notificationId;
                            form.appendChild(input);
                        }
                    }

                    document.getElementById('customModal').classList.remove('hidden');
                });
        }

// 2. ACCIÓN: SANCIONAR
        document.querySelectorAll('.js-btn-sancionar').forEach(btn => {
            btn.onclick = () => {
                const employeeId = btn.dataset.id;
                const notificationId = btn.dataset.notifId;
                if (typeof openGenerateSanctionModal === 'function') {
                    openGenerateSanctionModal(employeeId, notificationId);
                }
            };
        });

        // Botón regresar individual
        document.querySelectorAll('.js-btn-return').forEach(btn => {
            btn.onclick = () => {
                Swal.fire({
                    title: '¿Devolver trámite?',
                    text: "El registro volverá al estado inicial 'GENERADO'.",
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Sí, devolver',
                    cancelButtonText: 'Cancelar'
                }).then((result) => {
                    if (result.isConfirmed) executeAction(`/sanctions/notifications/${btn.dataset.id}/return/`);
                });
            };
        });

        // Botón asignar individual
        document.querySelectorAll('.js-assign-notification').forEach(btn => {
            btn.onclick = () => openAssignModal(btn.dataset.id);
        });
    }

    // --- 2. ABRIR MODAL E INICIALIZAR SELECT2 ---
    function openAssignModal(ids) {
        // Primero descargamos el HTML del modal
        fetch(`/sanctions/assign-ajax/?ids=${ids}`)
            .then(res => res.text())
            .then(html => {
                // 1. Insertamos el HTML en el DOM
                modalContent.innerHTML = html;
                customModal.classList.remove('hidden');

                // 2. AHORA QUE EL HTML YA EXISTE, inicializamos Select2
                const $select = $('#select-responsible-ajax');

                if ($select.length) {
                    $select.select2({
                        dropdownParent: $('#customModal'), // Obligatorio para que funcione dentro de modales
                        placeholder: 'Escriba cédula o nombre...',
                        minimumInputLength: 2,
                        width: '100%',
                        // Traducción manual a Español
                        language: {
                            inputTooShort: () => "Escriba 2 o más caracteres...",
                            noResults: () => "No se encontraron usuarios",
                            searching: () => "Buscando...",
                            errorLoading: () => "No se pudieron cargar los resultados"
                        },
                        ajax: {
                            // OJO: La URL según tu urls.py es '/sanctions/users/search/'
                            url: '/sanctions/users/search/',
                            dataType: 'json',
                            delay: 250,
                            data: params => ({q: params.term}),
                            processResults: data => ({results: data.results}),
                            cache: true
                        }
                    });

                    // Forzar el foco al abrir para que el usuario pueda escribir de inmediato
                    $select.on('select2:open', () => {
                        document.querySelector('.select2-search__field').focus();
                    });
                }
            })
            .catch(err => {
                console.error(err);
                Toast.fire({icon: 'error', title: 'Error al cargar el formulario de asignación'});
            });
    }

    // --- 3. ENVÍO DEL FORMULARIO DE ASIGNACIÓN (AJAX) ---
    document.addEventListener('submit', function (e) {
        if (e.target && e.target.id === 'assignNotificationForm') {
            e.preventDefault();
            const form = e.target;
            const formData = new FormData(form);

            if (!formData.get('assigned_to')) {
                Swal.fire({icon: 'warning', title: 'Atención', text: 'Debe seleccionar un responsable.'});
                return;
            }

            executeAction(form.action, formData);
        }
    });

    // Botones de cabecera
    if (massiveAssignBtn) massiveAssignBtn.onclick = () => openAssignModal(Array.from(selectedIds).join(','));

    if (massiveReturnBtn) {
        massiveReturnBtn.onclick = () => {
            Swal.fire({
                title: '¿Devolver seleccionados?',
                text: `Se devolverán ${selectedIds.size} trámites al estado inicial.`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, devolver todos'
            }).then((result) => {
                if (result.isConfirmed) {
                    const formData = new FormData();
                    formData.append('notification_ids', Array.from(selectedIds).join(','));
                    executeAction('/sanctions/notifications/massive-return/', formData);
                }
            });
        };
    }

    function fetchHistoryPage(page) {
        const month = document.getElementById('notifications-month').value;
        const year = document.getElementById('notifications-year').value;
        fetch(`${urlList}?page=${page}&notifications_month=${month}&notifications_year=${year}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                notificationsWrapper.innerHTML = data.html;
                bindEvents();
                updateMassiveButtons();
            });
    }

    function executeAction(url, formData = new FormData()) {
        const csrfToken = document.getElementById('csrf-token').value;
        if (!formData.has('csrfmiddlewaretoken')) formData.append('csrfmiddlewaretoken', csrfToken);

        Swal.fire({
            title: 'Procesando...', didOpen: () => {
                Swal.showLoading();
            }
        });

        fetch(url, {method: 'POST', body: formData})
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    customModal.classList.add('hidden'); // Cerrar modal si estaba abierto
                    Toast.fire({icon: 'success', title: data.message});
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                } else {
                    Swal.fire({icon: 'error', title: 'Error', text: data.message});
                }
            })
            .catch(() => Swal.fire({icon: 'error', title: 'Error de conexión'}));
    }

    bindEvents();
});