// Inicializador de permisos en wizard/dashboard de empleado:
// - detalle de permiso en modal
// - generar permiso con el mismo modal de la lista de permisos
// - tabla con filtros (desde/hasta/tipo) y paginacion local
(function () {
    function getCookie(name) {
        const cookieValue = document.cookie
            .split(';')
            .map((c) => c.trim())
            .find((c) => c.startsWith(name + '='));
        return cookieValue ? decodeURIComponent(cookieValue.split('=')[1]) : '';
    }

    function showToast(title, text, icon) {
        if (window.Swal) {
            Swal.fire({
                title: title,
                text: text,
                icon: icon,
                timer: 1800,
                showConfirmButton: false
            });
            return;
        }
        if (icon === 'error') {
            console.error(text);
        }
    }

    function fetchAndShow(url, containerSel) {
        if (!url) return;
        // Inserta el overlay directamente en <body> para evitar problemas de stacking
        // cuando el contenedor padre tiene transform/overflow que limita elementos fixed.
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(r => r.text())
            .then(html => {
                const text = String(html || '').trim();
                // Si el servidor devolvió JSON (error), parsear y mostrar toast en lugar de insertar overlay
                if (text.startsWith('{') || text.startsWith('[')) {
                    try {
                        const data = JSON.parse(text);
                        showToast('Error', data.message || data.error || 'Respuesta inesperada del servidor', 'error');
                    } catch (e) {
                        console.warn('fetchAndShow: respuesta no-HTML', e);
                    }
                    return;
                }

                // Limpiar overlays previos similares
                try {
                    const prev = document.querySelectorAll('#permission-modal-employee > .modal-overlay, body > .modal-overlay[data-source="permission-modal"]');
                    prev.forEach(p => p.remove());
                } catch (e) { /* ignore */ }

                const wrapper = document.createElement('div');
                wrapper.className = 'modal-overlay';
                wrapper.setAttribute('data-source', 'permission-modal');
                wrapper.innerHTML = html;

                // Añadir al body para asegurar posicionamiento fijo global
                document.body.appendChild(wrapper);
                document.body.classList.add('no-scroll');
            })
            .catch(e => console.error('Error cargando detalle permiso', e));
    }

    function openInsistModal(url) {
        if (!url) return;
        fetchAndShow(url, '#permission-modal-employee');
    }

    function initGeneratePermitForm(container) {
        const parentSelect = container.querySelector('#id_permit_type_parent');
        const subtypeContainer = container.querySelector('#subtype-container');
        const subtypeSelect = container.querySelector('#id_permit_type');
        const reasonSection = container.querySelector('#reason-section');
        const reasonTextarea = container.querySelector('#id_reason');
        const attachmentSection = container.querySelector('#attachment-section');
        const attachmentInput = container.querySelector('#id_justification_file');
        const startDateInput = container.querySelector('#id_start_date');
        const startTimeInput = container.querySelector('#id_start_time');
        const daysInput = container.querySelector('#id_days');
        const hoursInput = container.querySelector('#id_hours');
        const minutesInput = container.querySelector('#id_minutes');
        const calculatedEndSpan = container.querySelector('#calculated-end');
        const endDateHidden = container.querySelector('#id_end_date');
        const endTimeHidden = container.querySelector('#id_end_time');
        const form = container.querySelector('#generatePermitForm');

        if (!form || !parentSelect || !subtypeContainer || !subtypeSelect) return;

        parentSelect.addEventListener('change', async function () {
            const parentId = this.value;
            const selectedOption = this.options[this.selectedIndex];
            const needsJustification = selectedOption && selectedOption.dataset.needsJustification === 'true';
            const requiresAttachment = selectedOption && selectedOption.dataset.requiresAttachment === 'true';

            subtypeSelect.innerHTML = '<option value="">-- Cargando... --</option>';

            if (!parentId) {
                subtypeSelect.innerHTML = '<option value="">-- Primero seleccione tipo principal --</option>';
                subtypeContainer.style.display = 'none';
                if (reasonSection) reasonSection.style.display = 'none';
                if (attachmentSection) attachmentSection.style.display = 'none';
                if (reasonTextarea) reasonTextarea.required = false;
                if (attachmentInput) attachmentInput.required = false;
                return;
            }

            try {
                console.debug('initGeneratePermitForm: fetching subtypes for', parentId);
                const response = await fetch(`/permitrequest/api/subtypes/${parentId}/`, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
                const data = await response.json();
                console.debug('initGeneratePermitForm: subtypes response', data);

                subtypeSelect.innerHTML = '<option value="">-- Seleccione --</option>';

                if (data.success && data.subtypes && data.subtypes.length > 0) {
                    data.subtypes.forEach(subtype => {
                        const option = document.createElement('option');
                        option.value = subtype.id;
                        option.textContent = subtype.name;
                        option.dataset.needsJustification = subtype.needs_justification;
                        option.dataset.requiresAttachment = subtype.requires_attachment;
                        subtypeSelect.appendChild(option);
                    });

                    subtypeContainer.style.display = 'block';
                    subtypeSelect.required = true;
                    if (reasonSection) reasonSection.style.display = 'none';
                    if (attachmentSection) attachmentSection.style.display = 'none';
                    if (reasonTextarea) reasonTextarea.required = false;
                    if (attachmentInput) attachmentInput.required = false;
                } else {
                    subtypeContainer.style.display = 'none';
                    subtypeSelect.required = false;
                    subtypeSelect.innerHTML = `<option value="${parentId}" selected style="display:none;"></option>`;

                    if (reasonSection) reasonSection.style.display = needsJustification ? 'block' : 'none';
                    if (attachmentSection) attachmentSection.style.display = requiresAttachment ? 'block' : 'none';
                    if (reasonTextarea) reasonTextarea.required = !!needsJustification;
                    if (attachmentInput) attachmentInput.required = !!requiresAttachment;
                }
            } catch (error) {
                subtypeSelect.innerHTML = '<option value="">-- Error al cargar --</option>';
                subtypeContainer.style.display = 'none';
            }
        });

        subtypeSelect.addEventListener('change', function () {
            const selectedOption = this.options[this.selectedIndex];
            if (!selectedOption || !selectedOption.value) return;

            const needsJustification = selectedOption.dataset.needsJustification === 'true';
            const requiresAttachment = selectedOption.dataset.requiresAttachment === 'true';

            if (reasonSection) reasonSection.style.display = needsJustification ? 'block' : 'none';
            if (attachmentSection) attachmentSection.style.display = requiresAttachment ? 'block' : 'none';
            if (reasonTextarea) reasonTextarea.required = needsJustification;
            if (attachmentInput) attachmentInput.required = requiresAttachment;
        });

        function calculateEndDateTime() {
            if (!startDateInput || !startTimeInput || !daysInput || !hoursInput || !minutesInput || !calculatedEndSpan || !endDateHidden || !endTimeHidden) {
                return;
            }

            const startDate = startDateInput.value;
            const startTime = startTimeInput.value;
            const days = parseInt(daysInput.value, 10) || 0;
            const hours = parseInt(hoursInput.value, 10) || 0;
            const minutes = parseInt(minutesInput.value, 10) || 0;

            if (!startDate || !startTime) {
                calculatedEndSpan.textContent = '--';
                return;
            }

            const dt = new Date(`${startDate}T${startTime}`);
            dt.setDate(dt.getDate() + days);
            dt.setHours(dt.getHours() + hours);
            dt.setMinutes(dt.getMinutes() + minutes);

            const year = dt.getFullYear();
            const month = String(dt.getMonth() + 1).padStart(2, '0');
            const day = String(dt.getDate()).padStart(2, '0');
            const hour = String(dt.getHours()).padStart(2, '0');
            const minute = String(dt.getMinutes()).padStart(2, '0');

            calculatedEndSpan.textContent = `${day}/${month}/${year} ${hour}:${minute}`;
            endDateHidden.value = `${year}-${month}-${day}`;
            endTimeHidden.value = `${hour}:${minute}`;
        }

        [startDateInput, startTimeInput, daysInput, hoursInput, minutesInput].forEach(el => {
            if (el) el.addEventListener('change', calculateEndDateTime);
        });

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(form);

            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
                .then(async (res) => {
                    let data = {};
                    try {
                        data = await res.json();
                    } catch (_) {
                        data = {};
                    }

                    if (res.ok && data.success) {
                        const permContainer = document.getElementById('permission-modal-employee');
                        if (permContainer) permContainer.innerHTML = '';
                        document.body.classList.remove('no-scroll');
                        showToast('Guardado', data.message || 'Permiso generado correctamente', 'success');
                        setTimeout(() => window.location.reload(), 300);
                        return;
                    }

                    showToast('Error', data.message || 'No se pudo generar el permiso', 'error');
                })
                .catch(() => {
                    showToast('Error', 'Error de comunicacion al generar permiso', 'error');
                });
        });
    }

    function openGeneratePermitModal(employeeId) {
        const idStr = String(employeeId || '').trim();

        // Validar input para evitar placeholders como <id> o ejecuciones accidentales
        if (!idStr || /[<>]/.test(idStr) || !/^\d+$/.test(idStr)) {
            console.warn('openGeneratePermitModal: invalid employeeId', employeeId);
            showToast('Error', 'ID de empleado inválido', 'error');
            return;
        }

        const url = `/permitrequest/requests/generate/?employee=${encodeURIComponent(idStr)}`;
        console.debug('Fetching generate-permit URL:', url);

        // Evitar fetchs paralelos para el mismo employeeId
        window.__generatePermitInflight = window.__generatePermitInflight || new Set();
        if (window.__generatePermitInflight.has(idStr)) {
            console.warn('generate-permit already in flight for', idStr);
            return;
        }
        window.__generatePermitInflight.add(idStr);

        // Remover cualquier overlay previo antes de solicitar (reduce flash visual)
        try {
            const prev = document.querySelectorAll('body > .modal-overlay[data-source="permission-modal"]');
            prev.forEach(p => p.remove());
        } catch (e) { /* ignore */ }

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(r => r.text())
            .then(html => {
                const text = String(html || '').trim();
                if (text.startsWith('{') || text.startsWith('[')) {
                    try {
                        const data = JSON.parse(text);
                        showToast('Error', data.message || data.error || 'Respuesta inesperada del servidor', 'error');
                    } catch (e) {
                        console.warn('openGeneratePermitModal: respuesta no-HTML', e);
                    }
                    return;
                }

                try {
                    const prev = document.querySelectorAll('body > .modal-overlay[data-source="permission-modal"]');
                    prev.forEach(p => p.remove());
                } catch (e) { /* ignore */ }

                const wrapper = document.createElement('div');
                wrapper.className = 'modal-overlay';
                wrapper.id = 'permission-modal-employee';
                wrapper.setAttribute('data-source', 'permission-modal');
                wrapper.innerHTML = html;

                // Si el servidor devolviera el mismo formulario duplicado, conservar solo el primero
                try {
                    const containers = wrapper.querySelectorAll('.modal-container-medium');
                    if (containers.length > 1) {
                        for (let i = 1; i < containers.length; i++) containers[i].remove();
                    }
                } catch (e) { /* ignore */ }

                document.body.appendChild(wrapper);
                document.body.classList.add('no-scroll');

                initGeneratePermitForm(wrapper);
            })
            .catch((err) => {
                console.error('Error fetching generate permit form', err);
                showToast('Error', 'No se pudo cargar el formulario', 'error');
            })
            .finally(() => {
                try { window.__generatePermitInflight.delete(idStr); } catch (e) { /* ignore */ }
            });
    }

    function initPermissionHistoryTable(tableRoot) {
        if (!tableRoot || tableRoot.dataset.permissionsInit === '1') return;

        const fromInput = tableRoot.querySelector('[data-permission-date-from]');
        const toInput = tableRoot.querySelector('[data-permission-date-to]');
        const typeSelect = tableRoot.querySelector('[data-permission-type]');
        const tbody = tableRoot.querySelector('[data-permission-tbody]');
        const allRows = Array.from(tbody ? tbody.querySelectorAll('tr[data-permission-row]') : []);
        const pageInfo = tableRoot.querySelector('[data-permission-page-info]');
        const controlsWrap = tableRoot.querySelector('[data-permission-controls]');
        const firstBtn = tableRoot.querySelector('[data-permission-first]');
        const prevBtn = tableRoot.querySelector('[data-permission-prev]');
        const nextBtn = tableRoot.querySelector('[data-permission-next]');
        const lastBtn = tableRoot.querySelector('[data-permission-last]');
        const pageInput = tableRoot.querySelector('[data-permission-page-input]');
        const totalPagesBadge = tableRoot.querySelector('[data-permission-total-pages]');
        const clearBtn = tableRoot.querySelector('[data-permission-clear-btn]');
        const listLabel = tableRoot.querySelector('[data-permission-list-label]');
        const defaultListLabel = listLabel ? (listLabel.dataset.defaultLabel || listLabel.textContent.trim()) : '';
        let emptyRow = tbody ? tbody.querySelector('[data-permission-empty-row]') : null;

        const pageSize = 8;
        let currentPage = 1;

        function parseDate(value) {
            if (!value) return null;
            const d = new Date(`${value}T00:00:00`);
            return Number.isNaN(d.getTime()) ? null : d;
        }

        function formatInputDate(value) {
            if (!value) return '';
            const parts = value.split('-');
            if (parts.length !== 3) return value;
            return `${parts[2]}/${parts[1]}/${parts[0]}`;
        }

        function setDefaultCurrentMonthRange() {
            if (!fromInput || !toInput) return;
            if (fromInput.value || toInput.value) return;

            const now = new Date();
            const year = now.getFullYear();
            const month = now.getMonth();
            const firstDay = new Date(year, month, 1);
            const lastDay = new Date(year, month + 1, 0);

            const toISO = (d) => {
                const y = d.getFullYear();
                const m = String(d.getMonth() + 1).padStart(2, '0');
                const day = String(d.getDate()).padStart(2, '0');
                return `${y}-${m}-${day}`;
            };

            fromInput.value = toISO(firstDay);
            toInput.value = toISO(lastDay);
        }

        function ensureEmptyRow() {
            if (!tbody) return null;
            if (emptyRow) return emptyRow;

            emptyRow = document.createElement('tr');
            emptyRow.setAttribute('data-permission-empty-row', '1');
            emptyRow.innerHTML = `
                <td colspan="7" class="text-center py-5">
                    <i class="fas fa-inbox" style="font-size: 2.5rem; color: #cbd5e1;"></i>
                    <p class="text-muted mt-3 mb-0">No hay permisos para los filtros seleccionados.</p>
                </td>
            `;
            tbody.appendChild(emptyRow);
            return emptyRow;
        }

        function updateListLabel() {
            if (!listLabel) return;

            const fromVal = fromInput ? fromInput.value : '';
            const toVal = toInput ? toInput.value : '';

            if (fromVal && toVal) {
                listLabel.innerHTML = `<i class="fa-regular fa-calendar"></i> Listado de ${formatInputDate(fromVal)} hasta ${formatInputDate(toVal)}`;
                return;
            }
            if (fromVal) {
                listLabel.innerHTML = `<i class="fa-regular fa-calendar"></i> Listado desde ${formatInputDate(fromVal)}`;
                return;
            }
            if (toVal) {
                listLabel.innerHTML = `<i class="fa-regular fa-calendar"></i> Listado hasta ${formatInputDate(toVal)}`;
                return;
            }

            listLabel.innerHTML = `<i class="fa-regular fa-calendar"></i> ${defaultListLabel}`;
        }

        function getFilteredRows() {
            const fromDate = parseDate(fromInput && fromInput.value);
            const toDate = parseDate(toInput && toInput.value);
            const permitType = typeSelect ? typeSelect.value : '';

            return allRows.filter((row) => {
                const rowDate = parseDate(row.dataset.startDate || '');
                const rowType = row.dataset.permitType || '';

                if (fromDate && (!rowDate || rowDate < fromDate)) return false;
                if (toDate && (!rowDate || rowDate > toDate)) return false;
                if (permitType && rowType !== permitType) return false;
                return true;
            });
        }

        function render() {
            const filtered = getFilteredRows();
            const total = filtered.length;
            const totalPages = Math.max(1, Math.ceil(total / pageSize));
            currentPage = Math.min(currentPage, totalPages);

            const start = (currentPage - 1) * pageSize;
            const end = start + pageSize;
            const visible = filtered.slice(start, end);

            allRows.forEach(r => {
                r.style.display = 'none';
            });
            visible.forEach(r => {
                r.style.display = '';
            });

            const emptyStateRow = ensureEmptyRow();
            if (emptyStateRow) {
                emptyStateRow.style.display = total === 0 ? '' : 'none';
            }

            if (pageInfo) {
                const startIndex = total === 0 ? 0 : start + 1;
                const endIndex = Math.min(end, total);
                pageInfo.textContent = `Mostrando ${startIndex}-${endIndex} de ${total}`;
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
                totalPagesBadge.textContent = `de ${totalPages}`;
            }
            if (controlsWrap) {
                controlsWrap.style.visibility = noRows ? 'hidden' : 'visible';
            }

            updateListLabel();
        }

        function goToPage(page) {
            const filtered = getFilteredRows();
            const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
            let nextPage = parseInt(page, 10);
            if (Number.isNaN(nextPage)) nextPage = 1;
            if (nextPage < 1) nextPage = 1;
            if (nextPage > totalPages) nextPage = totalPages;
            currentPage = nextPage;
            render();
        }

        if (fromInput) {
            fromInput.addEventListener('change', () => {
                currentPage = 1;
                render();
            });
        }
        if (toInput) {
            toInput.addEventListener('change', () => {
                currentPage = 1;
                render();
            });
        }
        if (typeSelect) {
            typeSelect.addEventListener('change', () => {
                currentPage = 1;
                render();
            });
        }
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                if (fromInput) fromInput.value = '';
                if (toInput) toInput.value = '';
                if (typeSelect) typeSelect.value = '';
                setDefaultCurrentMonthRange();
                currentPage = 1;
                render();
            });
        }
        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                goToPage(currentPage - 1);
            });
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                goToPage(currentPage + 1);
            });
        }
        if (firstBtn) {
            firstBtn.addEventListener('click', () => goToPage(1));
        }
        if (lastBtn) {
            lastBtn.addEventListener('click', () => {
                const filtered = getFilteredRows();
                const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
                goToPage(totalPages);
            });
        }
        if (pageInput) {
            pageInput.addEventListener('change', () => goToPage(pageInput.value));
            pageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    goToPage(pageInput.value);
                }
            });
        }

        setDefaultCurrentMonthRange();
        render();
        tableRoot.dataset.permissionsInit = '1';
    }

    function bootPermissionWidgets() {
        const tableRoot = document.querySelector('[data-permission-history-table]');
        if (tableRoot) initPermissionHistoryTable(tableRoot);
    }

    function ensureDelegation() {
        if (window.__permissionDelegationBound) return;

        document.addEventListener('click', function (ev) {
            const detailLink = ev.target.closest && ev.target.closest('.open-permission');
            if (detailLink) {
                ev.preventDefault();
                const url = detailLink.dataset.url || (detailLink.dataset.id ? `/permissions/admin/${detailLink.dataset.id}/detail/` : null);
                fetchAndShow(url, '#permission-modal-employee');
                return;
            }

            const genBtn = ev.target.closest && ev.target.closest('.js-generate-permit-self');
            if (genBtn) {
                ev.preventDefault();
                openGeneratePermitModal(genBtn.dataset.employeeId);
                return;
            }

            const insistBtn = ev.target.closest && ev.target.closest('[data-permit-insist]');
            if (insistBtn) {
                ev.preventDefault();
                openInsistModal(insistBtn.dataset.insistUrl);
                return;
            }

            const closeBtn = ev.target.closest && ev.target.closest('.js-close-modal');
            if (closeBtn) {
                const permContainer = document.getElementById('permission-modal-employee');
                if (permContainer && permContainer.contains(closeBtn)) {
                    permContainer.innerHTML = '';
                    document.body.classList.remove('no-scroll');
                }
            }
        });

        document.addEventListener('submit', function (ev) {
            const form = ev.target;
            if (!form || form.id !== 'insistPermitForm') return;

            ev.preventDefault();

            const formData = new FormData(form);
            fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
                .then(async (res) => {
                    let data = {};
                    try {
                        data = await res.json();
                    } catch (_) {
                        data = {};
                    }

                    if (!res.ok || !data.success) {
                        showToast('Error', data.message || 'No se pudo insistir la solicitud', 'error');
                        return;
                    }

                    const permContainer = document.getElementById('permission-modal-employee');
                    if (permContainer) permContainer.innerHTML = '';
                    document.body.classList.remove('no-scroll');

                    showToast('Correcto', data.message || 'Solicitud insistida correctamente', 'success');
                    setTimeout(() => window.location.reload(), 350);
                })
                .catch(() => {
                    showToast('Error', 'Error de comunicacion al insistir la solicitud', 'error');
                });
        });

        window.__permissionDelegationBound = true;
    }

    function readyInit() {
        ensureDelegation();
        bootPermissionWidgets();

        const appContent = document.getElementById('app-content') || document.body;
        const observer = new MutationObserver(() => bootPermissionWidgets());
        observer.observe(appContent, {childList: true, subtree: true});

        setTimeout(() => {
            try {
                const bodyHasNoScroll = document.body.classList.contains('no-scroll');
                const visibleOverlay = Array.from(document.querySelectorAll('.modal-overlay')).some(o => {
                    return !o.classList.contains('hidden') && (getComputedStyle(o).display !== 'none');
                });
                if (bodyHasNoScroll && !visibleOverlay) {
                    document.body.classList.remove('no-scroll');
                }
            } catch (e) {
                console.warn('cleanup overlays error', e);
            }
        }, 120);
    }

    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        readyInit();
    } else {
        document.addEventListener('DOMContentLoaded', readyInit);
        window.addEventListener('load', readyInit);
    }

    window.openPermissionDetail = function (id) {
        const url = id ? `/permissions/admin/${id}/detail/` : null;
        if (url) fetchAndShow(url, '#permission-modal-employee');
    };
})();
