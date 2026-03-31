(function () {
    'use strict';

    function getCookie(name) {
        const cookieValue = document.cookie
            .split(';')
            .map((c) => c.trim())
            .find((c) => c.startsWith(name + '='));
        return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : '';
    }

    function showToast(icon, title, text) {
        if (window.Swal) {
            Swal.fire({
                icon: icon,
                title: title,
                text: text,
                timer: 1800,
                showConfirmButton: false
            });
            return;
        }
        if (icon === 'error') {
            console.error(text);
        }
    }

    function initBossPermitManager(root) {
        if (!root || root.dataset.bossPermitInit === '1') return;

        const tbody = root.querySelector('[data-boss-tbody]');
        const fromInput = root.querySelector('[data-boss-date-from]');
        const toInput = root.querySelector('[data-boss-date-to]');
        const statusInput = root.querySelector('[data-boss-status]');
        const lastnameInput = root.querySelector('[data-boss-lastname]');
        const clearBtn = root.querySelector('[data-boss-clear-btn]');
        const listLabel = root.querySelector('[data-boss-list-label]');

        const pageInfo = root.querySelector('[data-boss-page-info]');
        const controlsWrap = root.querySelector('[data-boss-controls]');
        const firstBtn = root.querySelector('[data-boss-first]');
        const prevBtn = root.querySelector('[data-boss-prev]');
        const nextBtn = root.querySelector('[data-boss-next]');
        const lastBtn = root.querySelector('[data-boss-last]');
        const pageInput = root.querySelector('[data-boss-page-input]');
        const totalPagesBadge = root.querySelector('[data-boss-total-pages]');

        const responseOverlay = document.getElementById('boss-permit-modal-response-overlay');
        const responseContainer = document.getElementById('boss-permit-modal-response-container');

        const pageSize = 8;
        let currentPage = 1;

        const rowMap = new Map();
        const rows = Array.from(tbody ? tbody.querySelectorAll('tr[data-boss-permit-row]') : []);
        rows.forEach((row) => {
            rowMap.set(row.dataset.permitId, row);
        });

        function parseDate(value) {
            if (!value) return null;
            const d = new Date(value + 'T00:00:00');
            return Number.isNaN(d.getTime()) ? null : d;
        }

        function formatInputDate(value) {
            if (!value) return '';
            const parts = value.split('-');
            if (parts.length !== 3) return value;
            return parts[2] + '/' + parts[1] + '/' + parts[0];
        }

        function ensureEmptyRow() {
            let emptyRow = tbody ? tbody.querySelector('[data-boss-empty-row]') : null;
            if (emptyRow) return emptyRow;
            if (!tbody) return null;

            emptyRow = document.createElement('tr');
            emptyRow.setAttribute('data-boss-empty-row', '1');
            emptyRow.innerHTML = '<td colspan="8" style="padding:22px;text-align:center;color:#64748b;">No existen permisos para los filtros seleccionados.</td>';
            tbody.appendChild(emptyRow);
            return emptyRow;
        }

        function getRows() {
            return Array.from(rowMap.values());
        }

        function getFilteredRows() {
            const fromDate = parseDate(fromInput && fromInput.value);
            const toDate = parseDate(toInput && toInput.value);
            const statusValue = statusInput ? statusInput.value : 'REQUESTED';
            const lastnameValue = lastnameInput ? lastnameInput.value.trim().toLowerCase() : '';

            return getRows().filter((row) => {
                const rowDate = parseDate(row.dataset.startDate || '');
                const rowStatus = row.dataset.status || '';
                const rowLastName = (row.dataset.lastName || '').toLowerCase();

                if (fromDate && (!rowDate || rowDate < fromDate)) return false;
                if (toDate && (!rowDate || rowDate > toDate)) return false;
                if (statusValue && rowStatus !== statusValue) return false;
                if (lastnameValue && rowLastName.indexOf(lastnameValue) === -1) return false;
                return true;
            });
        }

        function updateListLabel() {
            if (!listLabel) return;
            const fromVal = fromInput ? fromInput.value : '';
            const toVal = toInput ? toInput.value : '';

            if (fromVal && toVal) {
                listLabel.innerHTML = '<i class="fa-regular fa-calendar"></i> Listado de ' + formatInputDate(fromVal) + ' hasta ' + formatInputDate(toVal);
                return;
            }
            if (fromVal) {
                listLabel.innerHTML = '<i class="fa-regular fa-calendar"></i> Listado desde ' + formatInputDate(fromVal);
                return;
            }
            if (toVal) {
                listLabel.innerHTML = '<i class="fa-regular fa-calendar"></i> Listado hasta ' + formatInputDate(toVal);
                return;
            }
            listLabel.innerHTML = '<i class="fa-regular fa-calendar"></i> Listado de permisos de la unidad';
        }

        function buildStatusBadgeHtml(status) {
            if (status === 'APPROVED') {
                return '<span style="display:inline-flex; align-items:center; padding: 4px 8px; border-radius: 999px; background:#dcfce7; color:#166534; font-size:0.78rem; font-weight:700;">Aprobado</span>';
            }
            if (status === 'REJECTED') {
                return '<span style="display:inline-flex; align-items:center; padding: 4px 8px; border-radius: 999px; background:#fee2e2; color:#991b1b; font-size:0.78rem; font-weight:700;">Rechazado</span>';
            }
            return '<span style="display:inline-flex; align-items:center; padding: 4px 8px; border-radius: 999px; background:#fef3c7; color:#92400e; font-size:0.78rem; font-weight:700;">Solicitado</span>';
        }

        function buildActionsHtml(status, permitId) {
            let html = '';
            if (status === 'REQUESTED') {
                html += '<button type="button" data-boss-open-response data-action="approve" data-permit-id="' + permitId + '" style="border:none; width:30px; height:30px; border-radius:8px; background:#dcfce7; color:#166534; cursor:pointer;" title="Aprobar permiso"><i class="fas fa-check"></i></button>';
                html += '<button type="button" data-boss-open-response data-action="reject" data-permit-id="' + permitId + '" style="border:none; width:30px; height:30px; border-radius:8px; background:#fee2e2; color:#991b1b; cursor:pointer;" title="Rechazar permiso"><i class="fas fa-times"></i></button>';
            } else if (status === 'APPROVED') {
                html += '<a href="/permitrequest/admin/' + permitId + '/report/" target="_blank" style="display:inline-flex; align-items:center; justify-content:center; width:30px; height:30px; border-radius:8px; background:#dcfce7; color:#166534; text-decoration:none;" title="Imprimir permiso"><i class="fas fa-print"></i></a>';
            }
            html += '<a href="/permitrequest/admin/' + permitId + '/detail/" target="_blank" style="display:inline-flex; align-items:center; justify-content:center; width:30px; height:30px; border-radius:8px; background:#e2e8f0; color:#0f172a; text-decoration:none;" title="Ver detalle"><i class="fas fa-eye"></i></a>';
            return html;
        }

        function render() {
            const filtered = getFilteredRows();
            const total = filtered.length;
            const totalPages = Math.max(1, Math.ceil(total / pageSize));
            currentPage = Math.min(currentPage, totalPages);

            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;
            const visible = filtered.slice(start, end);

            getRows().forEach((r) => {
                r.style.display = 'none';
            });
            visible.forEach((r) => {
                r.style.display = '';
            });

            const emptyRow = ensureEmptyRow();
            if (emptyRow) {
                emptyRow.style.display = total === 0 ? '' : 'none';
            }

            if (pageInfo) {
                const startIndex = total === 0 ? 0 : start + 1;
                const endIndex = Math.min(end, total);
                pageInfo.textContent = 'Mostrando ' + startIndex + '-' + endIndex + ' de ' + total;
            }

            const noRows = total === 0;
            const disablePrev = currentPage <= 1 || noRows;
            const disableNext = currentPage >= totalPages || noRows;

            if (firstBtn) firstBtn.disabled = disablePrev;
            if (prevBtn) prevBtn.disabled = disablePrev;
            if (nextBtn) nextBtn.disabled = disableNext;
            if (lastBtn) lastBtn.disabled = disableNext;

            if (pageInput) {
                pageInput.value = String(currentPage);
                pageInput.max = String(totalPages);
            }
            if (totalPagesBadge) {
                totalPagesBadge.textContent = 'de ' + totalPages;
            }
            if (controlsWrap) {
                controlsWrap.style.visibility = noRows ? 'hidden' : 'visible';
            }

            updateListLabel();
        }

        function goToPage(page) {
            const totalRows = getFilteredRows().length;
            const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
            let nextPage = parseInt(page, 10);
            if (Number.isNaN(nextPage)) nextPage = 1;
            if (nextPage < 1) nextPage = 1;
            if (nextPage > totalPages) nextPage = totalPages;
            currentPage = nextPage;
            render();
        }

        function closeResponseModal() {
            if (!responseOverlay || !responseContainer) return;
            responseOverlay.classList.add('hidden');
            responseContainer.innerHTML = '';
            document.body.style.overflow = '';
        }

        function openResponseModal(permitId, action) {
            if (!responseOverlay || !responseContainer) return;
            const url = '/permitrequest/admin/' + permitId + '/' + action + '/';

            fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
                .then((res) => res.text())
                .then((html) => {
                    responseContainer.innerHTML = html;
                    responseOverlay.classList.remove('hidden');
                    document.body.style.overflow = 'hidden';

                    responseContainer.querySelectorAll('.js-close-response-modal').forEach((btn) => {
                        btn.addEventListener('click', closeResponseModal);
                    });

                    const form = responseContainer.querySelector('#responsePermitForm');
                    if (form) {
                        form.addEventListener('submit', function (e) {
                            e.preventDefault();
                            const formData = new FormData(form);
                            fetch(url, {
                                method: 'POST',
                                body: formData,
                                headers: {
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'X-CSRFToken': getCookie('csrftoken')
                                }
                            })
                                .then((r) => r.json())
                                .then((data) => {
                                    if (!data.success) {
                                        showToast('error', 'Error', data.message || 'No se pudo procesar el permiso');
                                        return;
                                    }

                                    closeResponseModal();

                                    const row = rowMap.get(String(permitId));
                                    if (row) {
                                        const nextStatus = data.status || (action === 'approve' ? 'APPROVED' : 'REJECTED');
                                        row.dataset.status = nextStatus;

                                        const cells = row.querySelectorAll('td');
                                        if (cells.length >= 8) {
                                            cells[5].innerHTML = buildStatusBadgeHtml(nextStatus);

                                            if (typeof data.response_note === 'string' && data.response_note.trim()) {
                                                cells[6].textContent = data.response_note;
                                            }

                                            const actionsWrap = cells[7].querySelector('div');
                                            if (actionsWrap) {
                                                actionsWrap.innerHTML = buildActionsHtml(nextStatus, permitId);
                                            }
                                        }
                                    }

                                    render();
                                    showToast('success', 'Correcto', data.message || 'Permiso procesado correctamente');
                                })
                                .catch(() => {
                                    showToast('error', 'Error', 'Error de comunicación con el servidor');
                                });
                        });
                    }
                })
                .catch(() => {
                    showToast('error', 'Error', 'No se pudo cargar el formulario de respuesta');
                });
        }

        if (fromInput) {
            fromInput.addEventListener('change', function () {
                currentPage = 1;
                render();
            });
        }
        if (toInput) {
            toInput.addEventListener('change', function () {
                currentPage = 1;
                render();
            });
        }
        if (statusInput) {
            statusInput.addEventListener('change', function () {
                currentPage = 1;
                render();
            });
        }
        if (lastnameInput) {
            lastnameInput.addEventListener('input', function () {
                currentPage = 1;
                render();
            });
        }
        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                if (fromInput) fromInput.value = '';
                if (toInput) toInput.value = '';
                if (statusInput) statusInput.value = 'REQUESTED';
                if (lastnameInput) lastnameInput.value = '';
                currentPage = 1;
                render();
            });
        }

        if (firstBtn) firstBtn.addEventListener('click', function () { goToPage(1); });
        if (prevBtn) prevBtn.addEventListener('click', function () { goToPage(currentPage - 1); });
        if (nextBtn) nextBtn.addEventListener('click', function () { goToPage(currentPage + 1); });
        if (lastBtn) {
            lastBtn.addEventListener('click', function () {
                const totalRows = getFilteredRows().length;
                const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
                goToPage(totalPages);
            });
        }
        if (pageInput) {
            pageInput.addEventListener('change', function () { goToPage(pageInput.value); });
            pageInput.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    goToPage(pageInput.value);
                }
            });
        }

        root.addEventListener('click', function (e) {
            const actionBtn = e.target.closest('[data-boss-open-response]');
            if (!actionBtn) return;
            e.preventDefault();
            const permitId = actionBtn.dataset.permitId;
            const action = actionBtn.dataset.action;
            if (!permitId || !action) return;
            openResponseModal(permitId, action);
        });

        if (responseOverlay) {
            responseOverlay.addEventListener('click', function (e) {
                if (e.target === responseOverlay) {
                    closeResponseModal();
                }
            });
        }

        render();
        root.dataset.bossPermitInit = '1';
    }

    function boot() {
        const manager = document.querySelector('[data-boss-permit-manager]');
        if (manager) initBossPermitManager(manager);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', boot);
    } else {
        boot();
    }
})();
