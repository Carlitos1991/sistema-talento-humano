// ==========================================
// MODAL GENÉRICO PARA TODO EL SISTEMA
// ==========================================
function openPayrollModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');

            // Inicializar Select2 dinámicamente si el modal lo requiere
            const modalOverlay = document.querySelector('.modal-overlay');
            if (modalOverlay) {
                $(modalOverlay).find('select').select2({
                    width: '100%',
                    dropdownParent: $(modalOverlay)
                });
                $(modalOverlay).find('input[type="text"]').addClass('input-field');
            }
        })
        .catch(error => console.error('Error cargando el modal:', error));
}

function closePayrollModal() {
    document.getElementById('modal-root').innerHTML = '';
    document.body.classList.remove('modal-open');
}

function submitPayrollForm(event) {
    event.preventDefault();
    const form = event.target;

    fetch(form.action, {
        method: 'POST',
        body: new FormData(form),
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                closePayrollModal();
                Swal.fire({
                    icon: 'success',
                    title: '¡Guardado!',
                    text: data.message,
                    timer: 1500,
                    showConfirmButton: false
                })
                    .then(() => location.reload());
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => Swal.fire('Error', 'Ocurrió un problema de comunicación.', 'error'));
}

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

// ---------- INCOME: modal + submit + toggle ----------
function openIncomeModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');

            // Inicializar select2 si hay selects
            $('#incomeForm select').select2({width: '100%', dropdownParent: $('#incomeModalOverlay')});
            $('#incomeForm input[type="text"]').addClass('input-field');

            // Lógica de acordeón para mapeo presupuestario
            const $incMappingCheckbox = $('#incomeForm input[name="has_mapping"]');
            const $incBudgetBox = $('#budgetMappingFields');
            $incMappingCheckbox.on('change', function () {
                if ($(this).is(':checked')) {
                    $incBudgetBox.slideDown(300);
                } else {
                    $incBudgetBox.slideUp(300);
                }
            });
        })
        .catch(error => console.error('Error cargando el modal de ingreso:', error));
}

function submitIncomeForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
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
                })
                    .then(() => location.reload());
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un problema con el servidor.', 'error');
        });
}

function toggleInactiveIncomes(showInactive) {
    fetch(`?show_inactive=${showInactive}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            const tbody = document.querySelector('.managed-table tbody');
            tbody.innerHTML = html;
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.renderTable === 'function') table._tableManager.renderTable();
            }
        })
        .catch(error => console.error('Error cargando la tabla de ingresos:', error));
}

// ---------- DEDUCTION: modal + submit + toggle ----------
function openDeductionModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');
            $('#deductionForm select').select2({width: '100%', dropdownParent: $('#deductionModalOverlay')});
            $('#deductionForm input[type="text"]').addClass('input-field');

            // Lógica de acordeón para mapeo presupuestario
            const $dedMappingCheckbox = $('#deductionForm input[name="has_mapping"]');
            const $dedBudgetBox = $('#budgetMappingFields');
            $dedMappingCheckbox.on('change', function () {
                if ($(this).is(':checked')) {
                    $dedBudgetBox.slideDown(300);
                } else {
                    $dedBudgetBox.slideUp(300);
                }
            });
        })
        .catch(error => console.error('Error cargando el modal de descuento:', error));
}

function submitDeductionForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
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
                })
                    .then(() => location.reload());
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un problema con el servidor.', 'error');
        });
}

function toggleInactiveDeductions(showInactive) {
    fetch(`?show_inactive=${showInactive}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            const tbody = document.querySelector('.managed-table tbody');
            tbody.innerHTML = html;
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.renderTable === 'function') table._tableManager.renderTable();
            }
        })
        .catch(error => console.error('Error cargando la tabla de descuentos:', error));
}

// ---------- ACCOUNT: modal + submit ----------
function openAccountModal(url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');

            // Inicializar select2 si existen selects dentro del modal
            $('#accountForm select').select2({width: '100%', dropdownParent: $('#accountModalOverlay')});
            $('#accountForm input[type="text"]').addClass('input-field');
        })
        .catch(error => console.error('Error cargando el modal de cuenta:', error));
}

function submitAccountForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                closeContributionModal();
                Swal.fire({icon: 'success', title: '¡Excelente!', text: data.message, timer: 1500, showConfirmButton: false})
                    .then(() => location.reload());
            } else {
                Swal.fire('Error', 'Por favor, revisa los datos ingresados.', 'error');
            }
        })
        .catch(error => {
            console.error(error);
            Swal.fire('Error', 'Ocurrió un problema con el servidor.', 'error');
        });
}

function toggleInactiveAccounts(showInactive) {
    fetch(`?show_inactive=${showInactive}`, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            const tbody = document.querySelector('.managed-table tbody');
            tbody.innerHTML = html;
            const table = document.querySelector('.managed-table');
            if (table && table._tableManager) {
                table._tableManager.originalRows = Array.from(tbody.querySelectorAll('tr'));
                table._tableManager.currentRows = [...table._tableManager.originalRows];
                if (typeof table._tableManager.renderTable === 'function') table._tableManager.renderTable();
            }
        })
        .catch(error => console.error('Error cargando la tabla de cuentas:', error));
}

// Añadimos placeholders dinámicamente cuando se abre el modal de cuentas
const _origOpenAccountModal = window.openAccountModal;
function openAccountModal(url) {
    // reutiliza la función genérica si existe
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            document.getElementById('modal-root').innerHTML = html;
            document.body.classList.add('modal-open');
            // Set placeholders
            const $code = $('#accountForm input[name="code"]');
            const $name = $('#accountForm input[name="name"]');
            const $desc = $('#accountForm textarea[name="description"]');
            if ($code.length) $code.attr('placeholder', 'Ej: 1000');
            if ($name.length) $name.attr('placeholder', 'Ej: Caja');
            if ($desc.length) $desc.attr('placeholder', 'Descripción de la cuenta (opcional)');
            $('#accountForm select').select2({width: '100%', dropdownParent: $('#accountModalOverlay')});
            $('#accountForm input[type="text"]').addClass('input-field');
        })
        .catch(error => console.error('Error cargando el modal de cuenta:', error));
}