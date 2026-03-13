// static/js/payslip_list.js

document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchInput');
    const tableContainer = document.getElementById('payslip-table-container');

    // 1. Motor de Búsqueda y Paginación AJAX
    function loadPayslips(page = 1) {
        if (!tableContainer) return;

        const query = searchInput ? searchInput.value : '';
        const url = `${window.URLS.baseList}?period_id=${window.CURRENT_PERIOD_ID}&q=${query}&page=${page}`;

        tableContainer.style.opacity = '0.5'; // Efecto de carga

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.json())
            .then(data => {
                tableContainer.innerHTML = data.html;
                tableContainer.style.opacity = '1';
            })
            .catch(err => {
                console.error('Error cargando roles:', err);
                tableContainer.style.opacity = '1';
            });
    }

    // 2. Buscador en tiempo real con Debounce (para no disparar 100 queries al escribir rápido)
    let searchTimeout = null;
    if (searchInput) {
        searchInput.addEventListener('keyup', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => loadPayslips(1), 300);
        });
    }

    // Exponer paginación
    window.loadTablePage = function (pageNum) {
        loadPayslips(pageNum);
    };

    // 3. Switch de Retención (Delegación de eventos: funciona incluso si el HTML se regenera)
    document.addEventListener('change', function (e) {
        if (e.target.matches('.toggle-withhold-btn')) {
            const payslipId = e.target.getAttribute('data-id');
            const isWithheld = e.target.checked;
            const toggleText = e.target.closest('.modern-toggle-wrapper').querySelector('.modern-toggle-text');

            let formData = new FormData();
            formData.append('is_withheld', isWithheld);
            formData.append('csrfmiddlewaretoken', window.CSRF_TOKEN);

            const toggleUrl = window.URLS.toggleWithhold.replace('999999', payslipId);

            fetch(toggleUrl, {method: 'POST', body: formData})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        toggleText.textContent = isWithheld ? 'Retenido' : 'Normal';
                    } else {
                        e.target.checked = !isWithheld; // Revertir visualmente
                        Swal.fire('Error', data.message || 'Error al procesar', 'error');
                    }
                });
        }
    });
});

// 4. Abrir y Cerrar Modal
window.openPayslipDetail = function (url) {
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.text())
        .then(html => {
            const container = document.getElementById('modal-container');
            if (container) {
                container.innerHTML = html;
                const modal = document.getElementById('payslipDetailModal');
                if (modal) {
                    modal.style.display = 'flex';
                    // Si el archivo JS del modal tiene una función de inicio, se llama aquí
                    if (typeof initPayslipModal === 'function') initPayslipModal();
                }
            }
        });
};

window.closePayslipDetail = function () {
    const modal = document.getElementById('payslipDetailModal');
    if (modal) modal.style.display = 'none';
};