document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS ---
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    const btnAdd = document.getElementById('btn-add-type');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias Modal
    const modalOverlay = document.getElementById('customModal');
    const modalContentContainer = document.getElementById('modal-dynamic-content');

    // --- EVENTOS ---

    // 1. Buscador
    let timeout = null;
    if (searchInput) {
        searchInput.addEventListener('keyup', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => fetchTableData(urlList + `?q=${e.target.value}`), 300);
        });
    }

    // 2. Abrir Modal (Botón Principal)
    if (btnAdd) {
        btnAdd.addEventListener('click', function () {
            openModal(this.dataset.url);
        });
    }

    // 3. Cerrar Modal desde overlay o botón cerrar
    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal')) {
                closeModal();
            }
        });
    }

    // 4. DELEGACIÓN DE ACCIONES EN LA TABLA (CRÍTICO)
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. EDITAR y CREAR SUB-ITEM (Abren el mismo modal)
            const modalBtn = e.target.closest('.js-edit') || e.target.closest('.js-add-sub');
            if (modalBtn) {
                e.preventDefault();
                openModal(modalBtn.dataset.url);
                return;
            }

            // B. TOGGLE STATUS (Baja/Alta)
            const toggleBtn = e.target.closest('.js-toggle');
            if (toggleBtn) {
                e.preventDefault();
                toggleStatus(toggleBtn.dataset.url);
                return;
            }

            // C. VER SUB-ITEMS (Recarga tabla con filtro)
            const viewSubsBtn = e.target.closest('.js-view-subs') || e.target.closest('.js-load-parent');
            if (viewSubsBtn) {
                e.preventDefault();
                fetchTableData(viewSubsBtn.dataset.url);
                return;
            }
        });
    }

    // --- FUNCIONES ---

    function openModal(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');

                initModalPlugins();

                const form = modalContentContainer.querySelector('form');
                if (form) form.addEventListener('submit', handleFormSubmit);
            })
            .catch(err => {
                console.error('Error al abrir modal:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
            });
    }

    function closeModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
    }

    function initModalPlugins() {
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                width: '100%',
                dropdownParent: modalOverlay
            });
        }
    }

    function handleFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        // Limpiar errores previos
        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async res => {
                const data = await res.json();
                if (res.ok) {
                    closeModal();
                    Swal.fire({
                        icon: 'success',
                        title: 'Guardado',
                        text: data.message || 'Operación exitosa',
                        timer: 2000,
                        showConfirmButton: false
                    });
                    fetchTableData(urlList);
                } else {
                    if (data.errors) showErrors(form, data.errors);
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
            if (result.isConfirmed) {
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
                            const Toast = Swal.mixin({
                                toast: true, position: 'top-end', showConfirmButton: false, timer: 3000
                            });
                            Toast.fire({icon: 'success', title: data.message});
                            fetchTableData(urlList);
                        }
                    })
                    .catch(err => {
                        console.error(err);
                        Swal.fire('Error', 'No se pudo cambiar el estado', 'error');
                    });
            }
        });
    }

    function fetchTableData(url) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                tableContainer.innerHTML = data.html;
            })
            .catch(err => {
                console.error('Error al cargar datos:', err);
            });
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
});
