document.addEventListener('DOMContentLoaded', () => {
    // Inicializar buscador en tiempo real
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            const rows = document.querySelectorAll('.table tbody tr');

            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    }
});

// Función para abrir el modal (AJAX)
function openPayrollModal(url) {
    const modalContainer = document.getElementById('modal-container');

    // SweetAlert Loading
    Swal.fire({
        title: 'Cargando...',
        text: 'Por favor espere',
        allowOutsideClick: false,
        didOpen: () => Swal.showLoading()
    });

    fetch(url, {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.text())
    .then(html => {
        Swal.close();
        modalContainer.innerHTML = html;
        const modalElement = document.getElementById('payrollModal');
        const bsModal = new bootstrap.Modal(modalElement);
        bsModal.show();
    })
    .catch(error => {
        Swal.close();
        console.error('Error:', error);
        Swal.fire('Error', 'No se pudo cargar el formulario.', 'error');
    });
}

// Enviar formulario (AJAX)
function submitPayrollForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    // Limpiar validaciones visuales
    form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));

    fetch(form.action, {
        method: 'POST',
        body: formData,
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            const modalElement = document.getElementById('payrollModal');
            const bsModal = bootstrap.Modal.getInstance(modalElement);
            bsModal.hide();

            Swal.fire({
                icon: 'success',
                title: '¡Guardado!',
                text: data.message,
                timer: 1500,
                showConfirmButton: false
            }).then(() => {
                location.reload();
            });
        } else {
            // Manejo de errores de validación
            if (data.errors) {
                let msg = '';
                for (const [key, value] of Object.entries(data.errors)) {
                    msg += `${value}\n`;
                    const input = form.querySelector(`[name="${key}"]`);
                    if(input) input.classList.add('is-invalid');
                }
                Swal.fire('Atención', msg, 'warning');
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire('Error', 'Error de comunicación con el servidor.', 'error');
    });
}

// Eliminar constante
function deleteConstant(url, name) {
    Swal.fire({
        title: `¿Eliminar ${name}?`,
        text: "Esto podría afectar cálculos de nómina futuros.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    Swal.fire('Eliminado', data.message, 'success').then(() => location.reload());
                } else {
                    Swal.fire('Error', data.message, 'error');
                }
            });
        }
    })
}