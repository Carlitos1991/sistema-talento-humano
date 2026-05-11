let currentActiveStatus = 'EN_PROCESO';

document.addEventListener('DOMContentLoaded', function () {
    const urlList = document.getElementById('url-list').value;
    const notificationsWrapper = document.getElementById('latest-notifications-wrapper');
    const csrfToken = document.getElementById('csrf-token')?.value;
    const selectedIds = new Set();

    const massiveAssignBtn = document.getElementById('btn-massive-assign');
    const massiveReturnBtn = document.getElementById('btn-massive-return');

    const Toast = Swal.mixin({
        toast: true, position: 'top-end', showConfirmButton: false, timer: 2500, timerProgressBar: true
    });

    // --- FUNCIONES GLOBALES ---
    window.filterSanctionsByStatus = function (status) {
        currentActiveStatus = status;
        selectedIds.clear();
        fetchHistoryPage(1);
    };

    window.updateStatsAndTable = function () {
        fetchHistoryPage(1);
    };

    function fetchHistoryPage(page) {
        const month = document.getElementById('notifications-month').value;
        const year = document.getElementById('notifications-year').value;
        const search = document.getElementById('notifications-search').value;

        let url = `${urlList}?page=${page}&status_filter=${currentActiveStatus}`;
        if (month) url += `&notifications_month=${month}`;
        if (year) url += `&notifications_year=${year}`;
        if (search) url += `&search_q=${encodeURIComponent(search)}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                if (notificationsWrapper) {
                    notificationsWrapper.innerHTML = data.html;
                    syncCheckboxes();
                }
                bindEvents();
                updateMassiveButtons();
                updatePaginationInfo(data.pagination);
                if (data.stats) updateStatsCards(data.stats);
            });
    }

    // --- MANEJO DE MODALES ---
    function safeSetHTML(id, html) {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = html;
            return true;
        }
        console.error(`Error: El elemento ID "${id}" no existe en el HTML.`);
        return false;
    }

    function closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.add('hidden');
            document.body.classList.remove('modal-open');
        }
    }

    function openModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('hidden');
            document.body.classList.add('modal-open');
        }
    }

    // ✅ FIX 1: Se agregó 'js-close-modal' al selector para cubrir los botones
    //           del modal de asignación (Cancelar y X).
    document.addEventListener('click', function (e) {
        const closeBtn = e.target.closest('[data-modal], .btn-cancel, .btn-close-modal, .close-modal, .js-close-modal');
        if (closeBtn) {
            // Intentar obtener el ID del modal desde data-modal o desde el overlay más cercano
            const modalId = closeBtn.dataset.modal || closeBtn.closest('.modal-overlay')?.id;
            if (modalId) {
                closeModal(modalId);
            }
        }
    });

    // --- ACCIONES ---

    function openGenerateSanctionModal(employeeId, notificationId = null) {
        let url = `/sanctions/generate/?employee_id=${employeeId}`;
        if (notificationId) url += `&notification_id=${notificationId}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                if (safeSetHTML('modal-dynamic-content', html)) {
                    openModal('customModal');
                    setTimeout(initModalPlugins, 200);
                }
            });
    }

    window.openSanctionHistoryModal = function (employeeId) {
        if (!employeeId) return;

        const url = `/sanctions/history/sanction-ajax/?employee_id=${employeeId}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => {
                if (!res.ok) throw new Error('Error 404: Ruta no encontrada');
                return res.json();
            })
            .then(data => {
                const container = document.getElementById('sanction-history-content');
                if (container && data.success) {
                    container.innerHTML = data.html;
                    openModal('sanctionHistoryModal');
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire({icon: 'error', title: 'Error', text: 'No se pudo cargar el historial de sanciones.'});
            });
    };

    window.openActionsHistoryModal = function (employeeId) {
        if (!employeeId) return;

        const url = `/sanctions/history/actions-ajax/?employee_id=${employeeId}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => {
                if (!res.ok) throw new Error('Error 404: Ruta no encontrada');
                return res.json();
            })
            .then(data => {
                const container = document.getElementById('actions-history-content');
                if (container && data.success) {
                    container.innerHTML = data.html;
                    openModal('actionsHistoryModal');
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire({icon: 'error', title: 'Error', text: 'No se pudo cargar el historial de acciones.'});
            });
    };

    function initModalPlugins() {
        // ✅ FIX 4: El select en modal_assign_notification.html tiene id="select-responsible-ajax",
        //           no la clase .js-authority-ajax. Se corrige el selector para que Select2 se monte.
        const $assignSelect = $('#select-responsible-ajax');
        if ($assignSelect.length) {
            $assignSelect.select2({
                dropdownParent: $('#customModal'),
                placeholder: 'Buscar responsable...',
                minimumInputLength: 2,
                width: '100%',
                ajax: {
                    url: '/sanctions/users/search/',
                    dataType: 'json',
                    data: p => ({q: p.term}),
                    processResults: d => ({results: d.results})
                }
            });
        }

        // Soporte para otros selects con la clase .js-authority-ajax (modal de sanciones)
        const $authoritySelect = $('.js-authority-ajax');
        if ($authoritySelect.length) {
            $authoritySelect.select2({
                dropdownParent: $('#customModal'),
                placeholder: 'Buscar autoridad...',
                minimumInputLength: 2,
                width: '100%',
                ajax: {
                    url: '/sanctions/users/search/',
                    dataType: 'json',
                    data: p => ({q: p.term}),
                    processResults: d => ({results: d.results})
                }
            });
        }

        const form = document.getElementById('generateSanctionForm');
        if (form) form.addEventListener('submit', handleSanctionFormSubmit);

        // Listener para el formulario de asignación bulk
        const assignForm = document.getElementById('assignNotificationForm');
        if (assignForm) {
            assignForm.addEventListener('submit', function (e) {
                e.preventDefault();
                const fd = new FormData(assignForm);
                executeAction(assignForm.action, fd, 'customModal');
            });
        }
    }

    function syncCheckboxes() {
        const checkboxes = document.querySelectorAll('.js-notification-checkbox');
        let allOnPageChecked = checkboxes.length > 0;

        checkboxes.forEach(cb => {
            if (selectedIds.has(cb.value)) {
                cb.checked = true;
            } else {
                cb.checked = false;
                allOnPageChecked = false;
            }
        });

        const checkAll = document.getElementById('check-all-notifications');
        if (checkAll && checkboxes.length > 0) {
            checkAll.checked = allOnPageChecked;
        }
    }

    // --- EVENTOS (bindEvents) ---
    function bindEvents() {
        // 1. Checkboxes
        const checkAll = document.getElementById('check-all-notifications');
        const checkboxes = document.querySelectorAll('.js-notification-checkbox');

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
                if (!this.checked && checkAll) checkAll.checked = false;
            };
        });

        // 2. Botones de Historiales
        document.querySelectorAll('.js-btn-sanction-history').forEach(btn => {
            btn.onclick = () => window.openSanctionHistoryModal(btn.dataset.employeeId);
        });

        document.querySelectorAll('.js-btn-actions-history').forEach(btn => {
            btn.onclick = () => window.openActionsHistoryModal(btn.dataset.employeeId);
        });

        // 3. Botones de Acción Individual
        document.querySelectorAll('.js-btn-sancionar').forEach(btn => {
            btn.onclick = () => openGenerateSanctionModal(btn.dataset.id, btn.dataset.notifId);
        });

        document.querySelectorAll('.js-assign-notification').forEach(btn => {
            btn.onclick = () => openAssignModal(btn.dataset.id);
        });

        // ✅ FIX 2: Botón Archivar — SweetAlert + llamada al backend ArchiveNotificationView
        document.querySelectorAll('.js-btn-archive').forEach(btn => {
            btn.onclick = () => {
                const notifId = btn.dataset.id;
                Swal.fire({
                    title: '¿Archivar trámite?',
                    text: 'Ingrese el motivo del archivo:',
                    input: 'textarea',
                    inputPlaceholder: 'Motivo del archivo...',
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Archivar',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: '#64748b',
                    inputValidator: (value) => {
                        if (!value || !value.trim()) return 'Debe ingresar un motivo.';
                    }
                }).then((result) => {
                    if (result.isConfirmed) {
                        const fd = new FormData();
                        fd.append('observation', result.value);
                        executeAction(`/sanctions/notifications/${notifId}/archive/`, fd);
                    }
                });
            };
        });

        // ✅ FIX 3: Botones Prev y Next de paginación — faltaban completamente
        const btnPrev = document.getElementById('history-btn-prev');
        if (btnPrev) {
            btnPrev.onclick = () => {
                const current = parseInt(document.getElementById('history-page-input').value) || 1;
                if (current > 1) fetchHistoryPage(current - 1);
            };
        }

        const btnNext = document.getElementById('history-btn-next');
        if (btnNext) {
            btnNext.onclick = () => {
                const current = parseInt(document.getElementById('history-page-input').value) || 1;
                const total = parseInt(document.getElementById('history-total-pages').textContent) || 1;
                if (current < total) fetchHistoryPage(current + 1);
            };
        }

        const btnFirst = document.getElementById('history-btn-first');
        if (btnFirst) btnFirst.onclick = () => fetchHistoryPage(1);

        const btnLast = document.getElementById('history-btn-last');
        if (btnLast) {
            btnLast.onclick = () => {
                const tot = parseInt(document.getElementById('history-total-pages').textContent);
                fetchHistoryPage(tot);
            };
        }

        // Ir a página escribiendo número
        const pageInput = document.getElementById('history-page-input');
        if (pageInput) {
            pageInput.onchange = function () {
                const total = parseInt(document.getElementById('history-total-pages').textContent) || 1;
                let page = parseInt(this.value) || 1;
                page = Math.max(1, Math.min(page, total));
                fetchHistoryPage(page);
            };
        }
    }

    // --- LÓGICA DE BOTONES MASIVOS ---
    function updateMassiveButtons() {
        const size = selectedIds.size;
        massiveAssignBtn?.classList.toggle('hidden', size === 0);
        massiveReturnBtn?.classList.toggle('hidden', size === 0);

        const countAssign = document.getElementById('count-assign');
        const countReturn = document.getElementById('count-return');
        if (countAssign) countAssign.textContent = size;
        if (countReturn) countReturn.textContent = size;
    }

    if (massiveAssignBtn) {
        massiveAssignBtn.onclick = () => {
            const ids = Array.from(selectedIds).join(',');
            const url = `/sanctions/notifications/assign/?ids=${ids}`;
            fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                .then(res => res.text())
                .then(html => {
                    document.getElementById('modal-dynamic-content').innerHTML = html;
                    openModal('customModal');
                    setTimeout(initModalPlugins, 200);
                });
        };
    }

    function updatePaginationInfo(pagination) {
        if (!pagination) return;
        const container = document.getElementById('history-js-pagination');
        if (container) container.style.display = (pagination.total_pages > 1) ? 'flex' : 'none';

        const info = document.getElementById('history-page-info');
        if (info) info.textContent = `Mostrando ${pagination.start_index} a ${pagination.end_index} de ${pagination.total_count}`;

        const input = document.getElementById('history-page-input');
        if (input) {
            input.value = pagination.current_page;
            input.max = pagination.total_pages;
        }

        const tot = document.getElementById('history-total-pages');
        if (tot) tot.textContent = pagination.total_pages;
    }

    if (massiveReturnBtn) {
        massiveReturnBtn.onclick = () => {
            const ids = Array.from(selectedIds).join(',');
            Swal.fire({
                title: `¿Devolver ${selectedIds.size} trámites?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, devolver',
                confirmButtonColor: '#f59e0b'
            }).then((result) => {
                if (result.isConfirmed) {
                    const fd = new FormData();
                    fd.append('notification_ids', ids); // ✅ FIX: el backend espera 'notification_ids'
                    executeAction(`/sanctions/notifications/massive-return/`, fd);
                }
            });
        };
    }

    // ✅ Se agregó parámetro opcional modalToClose para cerrar el modal tras acción exitosa
    function executeAction(url, formData = new FormData(), modalToClose = null) {
        formData.append('csrfmiddlewaretoken', csrfToken);
        fetch(url, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    if (modalToClose) closeModal(modalToClose);
                    Toast.fire({icon: 'success', title: data.message});
                    selectedIds.clear();
                    fetchHistoryPage(1);
                } else {
                    Swal.fire({icon: 'error', title: 'Error', text: data.message});
                }
            });
    }

    // Inicialización
    bindEvents();
});