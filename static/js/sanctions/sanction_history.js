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

    // --- FUNCIÓN PARA FILTRAR POR ESTADO ---
    window.filterSanctionsByStatus = function(status) {
        const month = document.getElementById('notifications-month').value;
        const year = document.getElementById('notifications-year').value;
        const search = document.getElementById('notifications-search').value;
        let url = `${urlList}?page=1`;
        
        // Agregar status_filter siempre (incluso 'all' para mostrar todos)
        url += `&status_filter=${status}`;
        
        if (month) url += `&notifications_month=${month}`;
        if (year) url += `&notifications_year=${year}`;
        if (search) url += `&search_q=${encodeURIComponent(search)}`;
        
        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                notificationsWrapper.innerHTML = data.html;
                bindEvents();
                // Limpiar selección de checkboxes
                selectedIds.clear();
                updateMassiveButtons();
                updatePaginationInfo(data.pagination);
                // Actualizar stats
                if (data.stats) {
                    updateStatsCards(data.stats);
                }
            })
            .catch(() => Swal.fire({icon: 'error', title: 'Error de conexión'}));
    };

    // --- FUNCIÓN PARA ACTUALIZAR STATS Y TABLA CUANDO CAMBIA MES/AÑO/BÚSQUEDA ---
    window.updateStatsAndTable = function() {
        const month = document.getElementById('notifications-month').value;
        const year = document.getElementById('notifications-year').value;
        const search = document.getElementById('notifications-search').value;
        const urlParams = new URLSearchParams(window.location.search);
        const currentStatus = urlParams.get('status_filter') || 'all';
        
        let url = `${urlList}?page=1&status_filter=${currentStatus}`;
        
        if (month) url += `&notifications_month=${month}`;
        if (year) url += `&notifications_year=${year}`;
        if (search) url += `&search_q=${encodeURIComponent(search)}`;
        
        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                notificationsWrapper.innerHTML = data.html;
                bindEvents();
                selectedIds.clear();
                updateMassiveButtons();
                updatePaginationInfo(data.pagination);
                // Actualizar stats sin recargar la página
                if (data.stats) {
                    updateStatsCards(data.stats);
                }
            })
            .catch(() => Swal.fire({icon: 'error', title: 'Error de conexión'}));
    };
    
    // --- FUNCIÓN PARA ACTUALIZAR LAS TARJETAS DE STATS EN EL DOM ---
    function updateStatsCards(statsData) {
        const statsRow = document.querySelector('.stats-row');
        if (!statsRow) return;
        
        // Reconstruir las stats cards
        statsRow.innerHTML = '';
        statsData.forEach(stat => {
            const statCard = document.createElement('div');
            statCard.className = `stat-card ${stat.class}`;
            statCard.onclick = function() {
                filterSanctionsByStatus(stat.filter_val);
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
        // Paginador - Input
        const pageInput = document.getElementById('notifications-page-input');
        if (pageInput) {
            pageInput.addEventListener('change', function () {
                fetchHistoryPage(parseInt(this.value) || 1);
            });
        }

        // Paginador - Botones
        const btnFirst = document.getElementById('btn-first');
        const btnPrev = document.getElementById('btn-prev');
        const btnNext = document.getElementById('btn-next');
        const btnLast = document.getElementById('btn-last');

        if (btnFirst) {
            btnFirst.onclick = () => {
                fetchHistoryPage(1);
            };
        }

        if (btnPrev) {
            btnPrev.onclick = () => {
                const current = parseInt(pageInput?.value || 1, 10);
                if (current > 1) {
                    fetchHistoryPage(current - 1);
                }
            };
        }

        if (btnNext) {
            btnNext.onclick = () => {
                const current = parseInt(pageInput?.value || 1, 10);
                const total = parseInt(pageInput?.max || 1, 10);
                if (current < total) {
                    fetchHistoryPage(current + 1);
                }
            };
        }

        if (btnLast) {
            btnLast.onclick = () => {
                const total = parseInt(pageInput?.max || 1, 10);
                fetchHistoryPage(total);
            };
        }

        // Filtros de mes y año (listener una sola vez, fuera de bindEvents)
        // Ver más abajo en el inicializador


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
            let url = `/sanctions/generate/?employee_id=${employeeId}`;
            if (notificationId) url += `&notification_id=${notificationId}`;

            fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                .then(res => res.text())
                .then(html => {
                    const modalContent = document.getElementById('modal-dynamic-content');
                    const modalOverlay = document.getElementById('customModal');

                    modalContent.innerHTML = html;
                    modalOverlay.classList.remove('hidden');
                    document.body.classList.add('modal-open');

                    // --- ESPERAR A QUE EL MODAL SEA VISIBLE PARA INICIALIZAR ---
                    setTimeout(() => {
                        $('.js-authority-ajax').select2({
                            dropdownParent: $('#customModal'),
                            placeholder: 'Escriba para buscar...',
                            minimumInputLength: 2,
                            width: '100%',
                            language: {
                                inputTooShort: () => "Escriba 2 o más caracteres...",
                                noResults: () => "No se encontraron resultados",
                                searching: () => "Buscando...",
                                errorLoading: () => "Error al cargar resultados"
                            },
                            ajax: {
                                url: '/sanctions/users/search/',
                                dataType: 'json',
                                delay: 250,
                                data: params => ({q: params.term}),
                                processResults: data => ({results: data.results}),
                                cache: true
                            }
                        });

                        // Vincular el evento de guardado
                        const form = document.getElementById('generateSanctionForm');
                        if (form) {
                            // Si tienes notificationId, lo inyectamos aquí
                            if (notificationId) {
                                const input = document.createElement('input');
                                input.type = 'hidden';
                                input.name = 'notification_id';
                                input.value = notificationId;
                                form.appendChild(input);
                            }
                            // IMPORTANTE: Asegúrate de tener la función handleSanctionFormSubmit definida
                            form.addEventListener('submit', handleSanctionFormSubmit);
                        }

                        // Inicializar acordeones si los hay
                        if (typeof initModalPlugins === 'function') initModalPlugins();

                    }, 200); // 200ms es tiempo suficiente para que el modal se muestre
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

        // Botones de historial
        document.querySelectorAll('.js-btn-sanction-history').forEach(btn => {
            btn.onclick = () => {
                const employeeId = btn.dataset.employeeId;
                openSanctionHistoryModal(employeeId);
            };
        });

        document.querySelectorAll('.js-btn-actions-history').forEach(btn => {
            btn.onclick = () => {
                const employeeId = btn.dataset.employeeId;
                openActionsHistoryModal(employeeId);
            };
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
        const search = document.getElementById('notifications-search').value;
        const urlParams = new URLSearchParams(window.location.search);
        const statusFilter = urlParams.get('status_filter') || 'all';
        
        let url = `${urlList}?page=${page}&status_filter=${statusFilter}`;
        
        if (month) url += `&notifications_month=${month}`;
        if (year) url += `&notifications_year=${year}`;
        if (search) url += `&search_q=${encodeURIComponent(search)}`;
        
        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                notificationsWrapper.innerHTML = data.html;
                bindEvents();
                updateMassiveButtons();
                updatePaginationInfo(data.pagination);
                // Actualizar stats también
                if (data.stats) {
                    updateStatsCards(data.stats);
                }
            });
    }

    function updatePaginationInfo(paginationData) {
        if (!paginationData) return;
        
        const pageInfo = document.getElementById('page-info');
        if (pageInfo) {
            pageInfo.textContent = `Mostrando ${paginationData.start_index} a ${paginationData.end_index} de ${paginationData.total_count}`;
        }
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

    // --- HISTORIAL DE SANCIONES Y ACCIONES ---
    function openSanctionHistoryModal(employeeId) {
        const sanctionHistoryModal = document.getElementById('sanctionHistoryModal');
        const sanctionHistoryContent = document.getElementById('sanction-history-content');

        fetch(`/sanctions/history/sanction-ajax/?employee_id=${employeeId}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    sanctionHistoryContent.innerHTML = data.html;
                    sanctionHistoryModal.classList.remove('hidden');
                } else {
                    Swal.fire({icon: 'error', title: 'Error', text: data.message});
                }
            })
            .catch(() => Swal.fire({icon: 'error', title: 'Error de conexión'}));
    }

    function openActionsHistoryModal(employeeId) {
        const actionsHistoryModal = document.getElementById('actionsHistoryModal');
        const actionsHistoryContent = document.getElementById('actions-history-content');

        fetch(`/sanctions/history/actions-ajax/?employee_id=${employeeId}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    actionsHistoryContent.innerHTML = data.html;
                    actionsHistoryModal.classList.remove('hidden');
                } else {
                    Swal.fire({icon: 'error', title: 'Error', text: data.message});
                }
            })
            .catch(() => Swal.fire({icon: 'error', title: 'Error de conexión'}));
    }

    // Cerrar modales de historial
    document.addEventListener('click', function (e) {
        const closeBtn = e.target.closest('[data-modal]');
        if (closeBtn) {
            const modalId = closeBtn.dataset.modal;
            const modal = document.getElementById(modalId);
            if (modal) {
                modal.classList.add('hidden');
            }
        }
    });

    // --- EVENT LISTENERS PARA FILTROS DE MES Y AÑO ---
    const monthFilter = document.getElementById('notifications-month');
    const yearFilter = document.getElementById('notifications-year');
    const searchInput = document.getElementById('notifications-search');
    
    let searchTimeout;
    
    if (monthFilter) {
        monthFilter.addEventListener('change', function () {
            updateStatsAndTable();
        });
    }
    
    if (yearFilter) {
        yearFilter.addEventListener('change', function () {
            updateStatsAndTable();
        });
    }
    
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                updateStatsAndTable();
            }, 500);
        });
    }

    bindEvents();
});