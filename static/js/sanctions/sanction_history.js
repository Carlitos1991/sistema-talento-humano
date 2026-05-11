let currentActiveStatus = 'EN_PROCESO';

document.addEventListener('DOMContentLoaded', function () {
    const urlList = document.getElementById('url-list').value;
    const notificationsWrapper = document.getElementById('latest-notifications-wrapper');
    const csrfToken = document.getElementById('csrf-token').value;
    const selectedIds = new Set();

    // Referencias UI Masivas
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

    // --- 1. EXPOSICIÓN DE FUNCIONES AL ÁMBITO GLOBAL (Solución ReferenceError) ---

    window.filterSanctionsByStatus = function (status) {
        currentActiveStatus = status;
        fetchHistoryPage(1);
    };

    window.updateStatsAndTable = function () {
        fetchHistoryPage(1);
    };

    // --- 2. MOTOR DE CARGA AJAX ---

    function fetchHistoryPage(page) {
        const month = document.getElementById('notifications-month').value;
        const year = document.getElementById('notifications-year').value;
        const search = document.getElementById('notifications-search').value;

        // Construcción de URL con persistencia de estado
        let url = `${urlList}?page=${page}&status_filter=${currentActiveStatus}`;
        if (month) url += `&notifications_month=${month}`;
        if (year) url += `&notifications_year=${year}`;
        if (search) url += `&search_q=${encodeURIComponent(search)}`;

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                // Actualizar Tabla
                notificationsWrapper.innerHTML = data.html;

                // Re-vincular eventos a los nuevos botones de la tabla
                bindEvents();

                // Limpiar selección masiva
                selectedIds.clear();
                updateMassiveButtons();

                // Actualizar Paginación y Cards
                updatePaginationInfo(data.pagination);
                if (data.stats) updateStatsCards(data.stats);
            })
            .catch(err => {
                console.error("Error en fetchHistoryPage:", err);
                Toast.fire({icon: 'error', title: 'Error al cargar los datos'});
            });
    }

    // --- 3. ACTUALIZACIÓN DINÁMICA DE LA INTERFAZ ---

    function updatePaginationInfo(pagination) {
        if (!pagination) return;

        const container = document.getElementById('history-js-pagination');
        if (container) {
            // MOSTRAR si hay más de 1 página, de lo contrario OCULTAR
            container.style.display = (pagination.total_pages > 1) ? 'flex' : 'none';
        }

        // Actualizar textos e input (usando IDs únicos 'history-')
        const pageInfo = document.getElementById('history-page-info');
        if (pageInfo) {
            pageInfo.textContent = `Mostrando ${pagination.start_index} a ${pagination.end_index} de ${pagination.total_count}`;
        }

        const pageInput = document.getElementById('history-page-input');
        if (pageInput) {
            pageInput.value = pagination.current_page;
            pageInput.max = pagination.total_pages;
        }

        const totalPagesLabel = document.getElementById('history-total-pages');
        if (totalPagesLabel) {
            totalPagesLabel.textContent = pagination.total_pages;
        }

        // Habilitar/Deshabilitar botones
        const btnFirst = document.getElementById('history-btn-first');
        const btnPrev = document.getElementById('history-btn-prev');
        const btnNext = document.getElementById('history-btn-next');
        const btnLast = document.getElementById('history-btn-last');

        if (btnFirst) btnFirst.disabled = !pagination.has_previous;
        if (btnPrev) btnPrev.disabled = !pagination.has_previous;
        if (btnNext) btnNext.disabled = !pagination.has_next;
        if (btnLast) btnLast.disabled = !pagination.has_next;
    }

    function updateStatsCards(statsData) {
        const statsRow = document.querySelector('.stats-row');
        if (!statsRow) return;

        statsRow.innerHTML = '';
        statsData.forEach(stat => {
            const card = document.createElement('div');
            card.className = `stat-card ${stat.class}`;
            card.onclick = () => window.filterSanctionsByStatus(stat.filter_val);
            card.innerHTML = `
                <div class="stat-left">
                    <h3>${stat.label}</h3>
                    <div class="number">${stat.count}</div>
                </div>
                <i class="fas ${stat.icon} stat-icon"></i>
            `;
            statsRow.appendChild(card);
        });
    }

    // --- 4. VINCULACIÓN DE EVENTOS ---

    function bindEvents() {
        // --- Paginación ---
        const pageInput = document.getElementById('history-page-input');
        if (pageInput) {
            pageInput.onchange = function () {
                fetchHistoryPage(parseInt(this.value) || 1);
            };
        }

        const btnFirst = document.getElementById('history-btn-first');
        if (btnFirst) btnFirst.onclick = () => fetchHistoryPage(1);

        const btnLast = document.getElementById('history-btn-last');
        if (btnLast) {
            btnLast.onclick = () => {
                const total = parseInt(document.getElementById('history-total-pages').textContent);
                fetchHistoryPage(total);
            };
        }

        const btnPrev = document.getElementById('history-btn-prev');
        if (btnPrev) {
            btnPrev.onclick = () => {
                const current = parseInt(document.getElementById('history-page-input').value);
                if (current > 1) fetchHistoryPage(current - 1);
            };
        }

        const btnNext = document.getElementById('history-btn-next');
        if (btnNext) {
            btnNext.onclick = () => {
                const current = parseInt(document.getElementById('history-page-input').value);
                const total = parseInt(document.getElementById('history-total-pages').textContent);
                if (current < total) fetchHistoryPage(current + 1);
            };
        }

        // --- Checkboxes y Selección Masiva ---
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

        // --- Acciones de Fila ---

        // Archivar
        document.querySelectorAll('.js-btn-archive').forEach(btn => {
            btn.onclick = () => {
                Swal.fire({
                    title: 'Archivar Notificación',
                    text: 'Escriba el motivo del archivo:',
                    input: 'textarea',
                    inputPlaceholder: 'Ej: El empleado justificó el atraso...',
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

        // Generar Sanción (Modal)
        document.querySelectorAll('.js-btn-sancionar').forEach(btn => {
            btn.onclick = () => openGenerateSanctionModal(btn.dataset.id, btn.dataset.notifId);
        });

        // Devolver Trámite
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
                    if (result.isConfirmed) {
                        executeAction(`/sanctions/notifications/${btn.dataset.id}/return/`);
                    }
                });
            };
        });

        // Asignar Individual
        document.querySelectorAll('.js-assign-notification').forEach(btn => {
            btn.onclick = () => {
                if (typeof openAssignModal === 'function') openAssignModal(btn.dataset.id);
            };
        });

        // Historiales (Modales)
        document.querySelectorAll('.js-btn-sanction-history').forEach(btn => {
            btn.onclick = () => {
                if (typeof openSanctionHistoryModal === 'function') openSanctionHistoryModal(btn.dataset.employeeId);
            };
        });

        document.querySelectorAll('.js-btn-actions-history').forEach(btn => {
            btn.onclick = () => {
                if (typeof openActionsHistoryModal === 'function') openActionsHistoryModal(btn.dataset.employeeId);
            };
        });
    }

    // --- 5. LOGICA DE ACCIONES Y MODALES ---

    function executeAction(url, formData = new FormData()) {
        formData.append('csrfmiddlewaretoken', csrfToken);
        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    Toast.fire({icon: 'success', title: data.message || 'Acción completada'});
                    fetchHistoryPage(1);
                } else {
                    Swal.fire({icon: 'error', title: 'Error', text: data.message});
                }
            });
    }

    function openGenerateSanctionModal(employeeId, notificationId = null) {
        let url = `/sanctions/generate/?employee_id=${employeeId}`;
        if (notificationId) url += `&notification_id=${notificationId}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                const dynamicContent = document.getElementById('modal-dynamic-content');
                const overlay = document.getElementById('customModal');

                dynamicContent.innerHTML = html;
                overlay.classList.remove('hidden');
                document.body.classList.add('modal-open');

                setTimeout(() => {
                    $('.js-authority-ajax').select2({
                        dropdownParent: $('#customModal'),
                        placeholder: 'Buscar autoridad...',
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

                    const form = document.getElementById('generateSanctionForm');
                    if (form) form.addEventListener('submit', handleSanctionFormSubmit);
                }, 200);
            });
    }

    function updateMassiveButtons() {
        const size = selectedIds.size;
        if (massiveAssignBtn) massiveAssignBtn.classList.toggle('hidden', size === 0);
        if (massiveReturnBtn) massiveReturnBtn.classList.toggle('hidden', size === 0);
        if (countAssign) countAssign.textContent = size;
        if (countReturn) countReturn.textContent = size;
    }

    // --- 6. FILTROS E INICIALIZACIÓN ---

    let searchTimeout;
    const searchInput = document.getElementById('notifications-search');
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(updateStatsAndTable, 500);
        });
    }

    // Cerrar modales al hacer clic fuera o en botones cerrar
    document.addEventListener('click', function (e) {
        if (e.target.closest('[data-modal]')) {
            const modalId = e.target.closest('[data-modal]').dataset.modal;
            document.getElementById(modalId).classList.add('hidden');
            document.body.classList.remove('modal-open');
        }
    });

    // Ejecutar vinculación inicial
    bindEvents();

    // Si el servidor ya envió datos de paginación inicial, actualizamos la UI
    if (window.initialNotificationsPagination) {
        updatePaginationInfo(window.initialNotificationsPagination);
    }
});