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
            openGuide(this.dataset.url);
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
            const editBtn = e.target.closest('.js-edit');
            if (editBtn) {
                e.preventDefault();
                openModal(editBtn.dataset.url);
                return;
            }

            const toggleBtn = e.target.closest('.js-toggle');
            if (toggleBtn) {
                e.preventDefault();
                toggleStatus(toggleBtn.dataset.url);
                return;
            }
        });
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

    function openGuide(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
            })
            .catch(err => {
                console.error('Error al abrir guía:', err);
                Swal.fire('Error', 'No se pudo cargar la guía', 'error');
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
