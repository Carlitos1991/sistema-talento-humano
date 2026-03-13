/* JS para cargar y controlar el modal usando las clases globales de style.css */

function openPayslipDetail(url) {
    // 1. Buscamos el HTML en el servidor
    fetch(url)
        .then(response => response.text())
        .then(html => {
            // 2. Inyectamos el HTML en el contenedor
            const container = document.getElementById('modal-container');
            container.innerHTML = html;

            // 3. Mostramos el modal quitando la clase 'hidden' global
            const backdrop = document.getElementById('payslipBackdrop');
            if (backdrop) {
                backdrop.classList.remove('hidden');
                document.body.classList.add('modal-open'); // Clase global para evitar scroll

                // 4. Activamos los botones
                initModalEvents(backdrop);
            }
        })
        .catch(error => console.error('Error cargando el modal del rol:', error));
}

function closeDetailModal() {
    const backdrop = document.getElementById('payslipBackdrop');
    if (backdrop) {
        // Volvemos a agregar la clase 'hidden' para ocultarlo
        backdrop.classList.add('hidden');
        document.body.classList.remove('modal-open');

        // Limpiamos el HTML para no dejar basura en el DOM
        setTimeout(() => {
            document.getElementById('modal-container').innerHTML = '';
        }, 300);
    }
}

function initModalEvents(backdrop) {
    // Cerrar al hacer clic fuera del contenedor blanco (en el overlay oscuro)
    backdrop.addEventListener('click', function (ev) {
        if (ev.target === backdrop) closeDetailModal();
    });

    // Delegación para botones de acción (Cerrar e Imprimir)
    const closeBtns = backdrop.querySelectorAll('[data-action="close"]');
    closeBtns.forEach(btn => btn.addEventListener('click', closeDetailModal));

    const printBtn = backdrop.querySelector('[data-action="print"]');
    if (printBtn) {
        printBtn.addEventListener('click', () => {
            // Aquí puedes lanzar un pop-up de impresión
            // Ej: window.open('tu_url_de_pdf', '_blank');
            window.print();
        });
    }
}

// Cerrar con la tecla Escape
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeDetailModal();
});

// Exponer globalmente
window.openPayslipDetail = openPayslipDetail;

/* =====================================================================
   LÓGICA PARA MODIFICAR RUBROS Y RETENER PAGOS
   ===================================================================== */

document.addEventListener('click', function (e) {
    // 1. EDICIÓN MANUAL DE RUBROS (El botón del lápiz)
    if (e.target.closest('.edit-item-btn')) {
        const btn = e.target.closest('.edit-item-btn');
        const itemId = btn.dataset.id;
        const currentVal = btn.dataset.val;
        const itemName = btn.dataset.name;

        // Pedimos el nuevo valor (Puedes cambiar prompt por Swal.fire si prefieres)
        let newVal = prompt(`Modificando: ${itemName}\nIngrese el nuevo valor exacto (Ej: 15.50):`, currentVal);

        if (newVal === null || newVal.trim() === "" || isNaN(newVal)) return;

        let formData = new FormData();
        formData.append('new_value', newVal);
        let csrfToken = getCookie('csrftoken');

        fetch(`/payroll/payslip-item/${itemId}/update/`, {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken},
            body: formData
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    // Actualizamos los números en pantalla con animación
                    document.getElementById(`item-val-${itemId}`).innerText = `$ ${parseFloat(newVal).toFixed(2)}`;

                    if (document.getElementById('total-ingresos'))
                        document.getElementById('total-ingresos').innerText = `$ ${parseFloat(data.new_total_income).toFixed(2)}`;
                    if (document.getElementById('total-egresos'))
                        document.getElementById('total-egresos').innerText = `$ ${parseFloat(data.new_total_deduction).toFixed(2)}`;
                    if (document.getElementById('liquido-pagar'))
                        document.getElementById('liquido-pagar').innerText = `$ ${parseFloat(data.new_net_pay).toFixed(2)}`;

                    // Notificamos al usuario
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            toast: true, position: 'top-end', showConfirmButton: false, timer: 3000,
                            icon: 'success', title: data.message
                        });
                    }
                } else {
                    alert("Error al actualizar: " + data.message);
                }
            });
    }
});

document.addEventListener('change', function (e) {
    // 2. SWITCH DE RETENCIÓN DE PAGO
    if (e.target.classList.contains('toggle-withhold-btn')) {
        const checkbox = e.target;
        const payslipId = checkbox.dataset.id;
        const isChecked = checkbox.checked;

        if (isChecked) {
            if (!confirm("¿Está seguro que desea RETENER el pago de este empleado? El rol no saldrá en el archivo de transferencias del banco.")) {
                checkbox.checked = false; // Canceló, devolvemos el switch a su lugar
                return;
            }
        }

        let csrfToken = getCookie('csrftoken');

        fetch(`/payroll/payslip/${payslipId}/toggle-withhold/`, {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({
                            toast: true, position: 'top-end', showConfirmButton: false, timer: 3000,
                            icon: 'success', title: data.message
                        });
                    }
                } else {
                    checkbox.checked = !isChecked; // Revertir si hubo error en backend
                    alert("Error de conexión");
                }
            });
    }
});

// Función de utilidad para obtener el CSRF Token en Django
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
