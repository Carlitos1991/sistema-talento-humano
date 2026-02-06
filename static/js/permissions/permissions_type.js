document.addEventListener('DOMContentLoaded', function () {

    // --- REFERENCIAS GLOBALES ---
    const tableContainer = document.getElementById('table-container');
    const searchInput = document.getElementById('searchInput');
    const btnAdd = document.getElementById('btn-add-type');
    const csrfToken = document.getElementById('csrf-token').value;
    const urlList = document.getElementById('url-list').value;

    // Referencias del Modal Personalizado
    const modalOverlay = document.getElementById('customModal');
    const modalContentContainer = document.getElementById('modal-dynamic-content');

    // --- EVENT LISTENERS ---

    // 1. Buscador (Debounce)
    let timeout = null;
    if (searchInput) {
        searchInput.addEventListener('keyup', function (e) {
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                fetchTableData(e.target.value);
            }, 300);
        });
    }

    // 2. Abrir Modal (Crear)
    if (btnAdd) {
        btnAdd.addEventListener('click', function () {
            const url = this.dataset.url;
            openModal(url);
        });
    }

    // 3. Cerrar Modal (Botón X o Click fuera)
    if (modalOverlay) {
        modalOverlay.addEventListener('click', function (e) {
            // Si clickea en el overlay (fondo oscuro) o en botón cerrar
            if (e.target === modalOverlay || e.target.closest('.js-close-modal')) {
                closeModal();
            }
        });
    }

    // 4. Delegación en Tabla (Editar / Eliminar)
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {
            // Editar
            const editBtn = e.target.closest('.js-edit');
            if (editBtn) {
                e.preventDefault();
                openModal(editBtn.dataset.url);
                return;
            }
            // Eliminar
            const deleteBtn = e.target.closest('.js-delete');
            if (deleteBtn) {
                e.preventDefault();
                confirmDelete(deleteBtn.dataset.url);
                return;
            }
        });
    }

    // --- FUNCIONES LOGICAS ---

    function openModal(url) {
        // Petición AJAX para obtener el HTML del formulario
        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(response => response.text())
            .then(html => {
                // Inyectar HTML
                modalContentContainer.innerHTML = html;

                // Mostrar Modal (CSS Class)
                modalOverlay.style.display = 'flex';
                // Pequeño delay para permitir transición de opacidad
                setTimeout(() => {
                    modalOverlay.classList.add('is-visible');
                }, 10);

                // Inicializar Plugins (Select2)
                initModalPlugins();

                // Interceptar el Submit del Formulario
                const form = modalContentContainer.querySelector('form');
                if (form) {
                    form.addEventListener('submit', handleFormSubmit);
                }
            });
    }

    function closeModal() {
        modalOverlay.classList.remove('is-visible');
        // Esperar a que termine la transición CSS para ocultar display
        setTimeout(() => {
            modalOverlay.style.display = 'none';
            modalContentContainer.innerHTML = ''; // Limpiar memoria
        }, 300);
    }

    function initModalPlugins() {
        // Inicializar Select2 si existe jQuery disponible (requerido por Select2)
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                width: '100%',
                // Importante: No usar dropdownParent si da problemas con z-index fuera de bootstrap,
                // pero usualmente ayuda a que el select se vea dentro del modal.
            });
        }
    }

    function handleFormSubmit(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        const actionUrl = form.action;

        // Limpiar errores visuales
        clearFormErrors(form);

        fetch(actionUrl, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async response => {
                const data = await response.json();

                if (response.ok) { // Éxito
                    closeModal();
                    Swal.fire({
                        icon: 'success',
                        title: 'Guardado',
                        text: data.message,
                        timer: 1500,
                        showConfirmButton: false
                    });
                    fetchTableData(searchInput.value); // Recargar tabla
                } else { // Error de validación (400)
                    if (data.errors) {
                        showFormErrors(form, data.errors);
                    }
                }
            })
            .catch(error => {
                console.error('Error:', error);
                Swal.fire('Error', 'Error de conexión', 'error');
            });
    }

    function fetchTableData(query = '') {
        const url = `${urlList}?q=${query}`;
        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(response => response.json())
            .then(data => {
                tableContainer.innerHTML = data.html;
            });
    }

    function confirmDelete(url) {
        Swal.fire({
            title: '¿Eliminar registro?',
            text: "No podrás deshacer esta acción",
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#aaa',
            confirmButtonText: 'Sí, eliminar',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': csrfToken
                    }
                })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) {
                            Swal.fire('Eliminado', data.message, 'success');
                            fetchTableData(searchInput.value);
                        }
                    });
            }
        })
    }

    // Funciones Auxiliares de Error UI
    function showFormErrors(form, errors) {
        // Errores generales
        if (errors.__all__) {
            const errorBox = document.getElementById('global-errors');
            if (errorBox) {
                errorBox.textContent = errors.__all__.join(', ');
                errorBox.style.display = 'block';
            }
        }
        // Errores por campo
        for (const [field, messages] of Object.entries(errors)) {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('input-error');
                // Crear o actualizar mensaje
                let msgDiv = input.parentNode.querySelector('.error-msg');
                if (!msgDiv) {
                    msgDiv = document.createElement('span');
                    msgDiv.className = 'error-msg';
                    input.parentNode.appendChild(msgDiv);
                }
                msgDiv.textContent = messages.join(', ');
            }
        }
    }

    function clearFormErrors(form) {
        form.querySelectorAll('.input-error').forEach(el => el.classList.remove('input-error'));
        form.querySelectorAll('.error-msg').forEach(el => el.remove());
        const globalErr = document.getElementById('global-errors');
        if (globalErr) globalErr.style.display = 'none';
    }
});