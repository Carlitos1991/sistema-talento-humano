// Función para abrir el modal de creación (Estático)
document.addEventListener('DOMContentLoaded', function () {
    const btnAdd = document.getElementById('btn-add-level');
    if (btnAdd) {
        btnAdd.addEventListener('click', function () {
            const modal = document.getElementById('levelModal');
            modal.classList.remove('hidden');
        });
    }
});

// Función para abrir el modal de edición (Vía AJAX para cargar datos)
window.openEditLevel = function (id) {
    // Si prefieres cargar el formulario con datos ya llenos desde el servidor:
    const url = `/institution/levels/edit/${id}/`; // Ajusta a tu URL real
    openAjaxModal(url, '#levelModal');
};

// Función para cerrar el modal (si no usas la de main.js)
window.closeLevelModal = function () {
    document.getElementById('levelModal').classList.add('hidden');
};

// Función para cambiar estado (Activar/Desactivar)
window.toggleLevelStatus = function (btn, url, name) {
    const action = btn.title.toLowerCase();
    Swal.fire({
        title: `¿${action.charAt(0).toUpperCase() + action.slice(1)} nivel?`,
        text: `Vas a cambiar el estado de: ${name}`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Sí, cambiar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#059669'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCSRF(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire('¡Hecho!', data.message, 'success').then(() => location.reload());
                    }
                });
        }
    });
};