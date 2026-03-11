// 1. Abrir Modal
function openContributionModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            // Inyectamos el HTML
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');

            // ==========================================
            // A. INICIALIZAR SELECT2 CON JQUERY
            // ==========================================
            $('#contributionForm select').select2({
                width: '100%',
                // El dropdownParent evita que el buscador de Select2 se esconda detrás del modal
                dropdownParent: $('#contributionModalOverlay')
            });

            // Forzar la clase de tu diseño a los inputs nativos
            $('#contributionForm input[type="text"]').addClass('input-field');

            // ==========================================
            // B. LÓGICA DE ACORDEÓN (ANIMACIÓN SUAVE)
            // ==========================================
            const $mappingCheckbox = $('#contributionForm input[name="has_mapping"]');
            const $budgetFieldsBox = $('#budgetMappingFields');

            $mappingCheckbox.on('change', function () {
                if ($(this).is(':checked')) {
                    // Se desliza hacia abajo (abre)
                    $budgetFieldsBox.slideDown(300);
                } else {
                    // Se desliza hacia arriba (cierra)
                    $budgetFieldsBox.slideUp(300);
                }
            });
        })
        .catch(error => console.error('Error cargando el modal:', error));
}

// 2. Cerrar Modal
function closeContributionModal() {
    document.getElementById('modal-root').innerHTML = '';
    document.body.classList.remove('modal-open');
}

// 3. Enviar Formulario por AJAX
function submitContributionForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                closeContributionModal();
                Swal.fire({
                    icon: 'success',
                    title: '¡Excelente!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                }).then(() => {
                    location.reload();
                });
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un problema de comunicación con el servidor.', 'error');
        });
}

// 4. Cargar tabla parcial sin recargar la página (AJAX)
function toggleInactiveContributions(showInactive) {
    // Hacemos la petición silenciosa a la vista
    fetch(`?show_inactive=${showInactive}`, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(response => response.text())
        .then(html => {
            // Reemplazamos el cuerpo de la tabla con las nuevas filas
            const tbody = document.querySelector('.managed-table tbody');
            tbody.innerHTML = html;

            // Reiniciamos el paginador y buscador (table-manager.js)
            // para que cuente las nuevas filas renderizadas
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.renderTable === 'function') {
                    table._tableManager.renderTable();
                }
            }
        })
        .catch(error => console.error('Error cargando la tabla:', error));
}