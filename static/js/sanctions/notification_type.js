document.addEventListener('DOMContentLoaded', function () {
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const btnAdd = document.getElementById('btn-add-type');
    const btnGuide = document.getElementById('btn-guide');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;
    const modalOverlay = document.getElementById('customModal');
    const modalContentContainer = document.getElementById('modal-dynamic-content');
    const pageInfo = document.getElementById('page-info');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const currentPageDisplay = document.getElementById('current-page-display');

    let currentPage = 1;
    let totalPages = 1;
    let timeout = null;

    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                currentPage = 1;
                fetchTableData(urlList + `?q=${encodeURIComponent(e.target.value)}&page=1`);
            }, 300);
        });
    }

    if (btnAdd) {
        btnAdd.addEventListener('click', function () {
            openModal(this.dataset.url);
        });
    }

    if (btnGuide) {
        btnGuide.addEventListener('click', function () {
            openPreview(this.dataset.url);
        });
    }

    if (btnPrev) {
        btnPrev.addEventListener('click', () => {
            if (currentPage > 1) {
                const searchQuery = searchInput ? searchInput.value : '';
                const url = urlList + `?page=${currentPage - 1}${searchQuery ? '&q=' + encodeURIComponent(searchQuery) : ''}`;
                fetchTableData(url);
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', () => {
            if (currentPage < totalPages) {
                const searchQuery = searchInput ? searchInput.value : '';
                const url = urlList + `?page=${currentPage + 1}${searchQuery ? '&q=' + encodeURIComponent(searchQuery) : ''}`;
                fetchTableData(url);
            }
        });
    }

    fetchTableData(urlList + '?page=1');

    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal')) {
                closeModal();
            }
        });
    }

    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {
            const templateListBtn = e.target.closest('.js-open-template-list');
            if (templateListBtn) {
                e.preventDefault();
                openTemplateListModal(templateListBtn);
                return;
            }

            const editBtn = e.target.closest('.js-edit');
            if (editBtn) {
                e.preventDefault();
                openModal(editBtn.dataset.url);
                return;
            }

            const previewBtn = e.target.closest('.js-preview');
            if (previewBtn) {
                e.preventDefault();
                openPreview(previewBtn.dataset.url);
                return;
            }

            const toggleBtn = e.target.closest('.js-toggle');
            if (toggleBtn) {
                e.preventDefault();
                toggleStatus(toggleBtn.dataset.url);
                return;
            }

            const templateRow = e.target.closest('.js-template-row');
            if (templateRow && !e.target.closest('a, button')) {
                e.preventDefault();
                const editUrl = templateRow.dataset.editUrl;
                if (editUrl) {
                    window.location.href = editUrl;
                }
            }
        });
    }

    function openTemplateListModal(triggerBtn) {
        const typeId = triggerBtn.dataset.typeId;
        const typeName = triggerBtn.dataset.typeName || 'Tipo de notificación';
        const dataSource = document.getElementById(`template-data-${typeId}`);

        if (!dataSource) {
            Swal.fire('Sin datos', 'No se pudo obtener la lista de templates.', 'warning');
            return;
        }

        const items = Array.from(dataSource.querySelectorAll('.template-data-item')).map((item) => ({
            templateId: item.dataset.templateId,
            editUrl: item.dataset.editUrl,
            createUrl: item.dataset.createUrl,
            hasTemplate: item.dataset.hasTemplate === '1',
            regimeCode: item.dataset.regimeCode,
            regimeName: item.dataset.regimeName,
            regimeId: item.dataset.regimeId
        }));

        const rowsHtml = items.length
            ? items.map((item) => `
                <div class="template-list-row js-template-row" data-edit-url="${item.editUrl || ''}" data-create-url="${item.createUrl || ''}">
                    <div class="template-list-main">
                        <span class="template-regime-code">${escapeHtml(item.regimeCode || '')}</span>
                        <span class="template-regime-name">${escapeHtml(item.regimeName || '')}</span>
                        ${item.hasTemplate
                            ? '<span class="status-badge active">Plantilla creada</span>'
                            : '<span class="status-badge inactive">Sin plantilla</span>'}
                    </div>
                    <div class="template-list-actions">
                        ${item.hasTemplate
                            ? `
                                <a href="${item.editUrl}" class="btn-views-action" title="Editar plantilla" style="text-decoration: none;">
                                    <i class="fa-solid fa-pen"></i>
                                </a>
                                <a href="${item.editUrl}" target="_blank" rel="noopener" class="btn-detail-action" title="Abrir en nueva pestaña" style="text-decoration: none;">
                                    <i class="fa-solid fa-up-right-from-square"></i>
                                </a>
                            `
                            : `
                                <a href="${item.createUrl}" class="btn-create-action" title="Crear plantilla" style="text-decoration: none;">
                                    <i class="fa-solid fa-plus"></i> 
                                </a>
                            `}
                    </div>
                </div>
            `).join('')
            : '<div class="template-list-empty">No hay regímenes asociados a este tipo de notificación.</div>';

        modalContentContainer.innerHTML = `
            <div class="modal-box templates-modal-box">
                <div class="modal-header">
                    <h3 class="modal-title">Templates de ${escapeHtml(typeName)}</h3>
                    <button type="button" class="btn-close js-close-modal" aria-label="Cerrar">&times;</button>
                </div>
                <div class="modal-body templates-modal-body">
                    <div class="template-list-header">
                        <span>${items.length} régimen(es) seleccionado(s)</span>
                        <small>Si no existe plantilla, puedes crearla desde aquí</small>
                    </div>
                    <div class="template-list-container">
                        ${rowsHtml}
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary js-close-modal">Cerrar</button>
                </div>
            </div>
        `;

        modalOverlay.classList.remove('hidden');
    }

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function openModal(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                initModal();
                const form = modalContentContainer.querySelector('form');
                if (form) form.addEventListener('submit', handleFormSubmit);
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }

    function openPreview(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                initModal();
            })
            .catch(err => {
                console.error('Error al abrir vista previa:', err);
                Swal.fire('Error', 'No se pudo cargar la vista previa', 'error');
            });
    }

    function closeModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
    }

    function initModal() {
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({width: '100%', dropdownParent: modalOverlay});
        }
    }

    function handleFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        clearErrors(form);

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async res => {
                const data = await res.json().catch(() => ({}));
                if (res.ok && data.success) {
                    closeModal();
                    const Toast = Swal.mixin({toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true});
                    Toast.fire({icon: 'success', title: data.message || 'Operación exitosa'});
                    const searchQuery = searchInput ? searchInput.value : '';
                    fetchTableData(urlList + `?page=${currentPage}${searchQuery ? '&q=' + encodeURIComponent(searchQuery) : ''}`);
                    return;
                }

                if (res.status === 403) {
                    Swal.fire('Acceso denegado', data.message || 'No tiene permisos para realizar esta acción', 'error');
                    return;
                }

                if (data.errors) {
                    showErrors(form, data.errors);
                } else {
                    Swal.fire('Error', data.message || 'Ocurrió un error al guardar', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }

    function toggleStatus(url) {
        Swal.fire({
            title: '¿Cambiar estado?',
            text: 'Se alternará entre activo e inactivo',
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, cambiar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#3085d6',
            cancelButtonColor: '#d33'
        }).then((result) => {
            if (!result.isConfirmed) return;

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        const Toast = Swal.mixin({toast: true, position: 'top-end', showConfirmButton: false, timer: 3000, timerProgressBar: true});
                        Toast.fire({icon: 'success', title: data.message});
                        const searchQuery = searchInput ? searchInput.value : '';
                        fetchTableData(urlList + `?page=${currentPage}${searchQuery ? '&q=' + encodeURIComponent(searchQuery) : ''}`);
                    }
                })
                .catch(err => {
                    console.error(err);
                    Swal.fire('Error', 'No se pudo cambiar el estado', 'error');
                });
        });
    }

    function fetchTableData(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                tableContainer.innerHTML = data.html;
                if (data.pagination) {
                    updatePagination(data.pagination);
                }
            })
            .catch(err => console.error('Error al cargar datos:', err));
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

        if (btnPrev) btnPrev.disabled = !paginationData.has_previous;
        if (btnNext) btnNext.disabled = !paginationData.has_next;
    }

    function clearErrors(form) {
        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => {
            el.style.display = '';
            el.textContent = '';
        });
        const globalErrors = form.querySelector('#global-errors');
        if (globalErrors) {
            globalErrors.style.display = 'none';
            globalErrors.textContent = '';
        }
        const regimeErrors = form.querySelector('#regime-errors');
        if (regimeErrors) {
            regimeErrors.style.display = 'none';
            regimeErrors.textContent = '';
        }
    }

    function showErrors(form, errors) {
        let globalMessages = [];
        Object.entries(errors).forEach(([field, msgs]) => {
            const messages = Array.isArray(msgs) ? msgs : [msgs];
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('is-invalid');
                const feedback = input.parentNode ? input.parentNode.querySelector('.invalid-feedback') : null;
                if (feedback) {
                    feedback.textContent = messages.join(' ');
                    feedback.style.display = 'block';
                } else {
                    globalMessages = globalMessages.concat(messages);
                }
            } else {
                globalMessages = globalMessages.concat(messages);
            }
        });

        const globalErrors = form.querySelector('#global-errors');
        if (globalErrors && globalMessages.length) {
            globalErrors.style.display = 'block';
            globalErrors.textContent = globalMessages.join(' ');
        }
    }
});
