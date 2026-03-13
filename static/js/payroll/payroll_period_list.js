// static/js/payroll_period_list.js

document.addEventListener("DOMContentLoaded", function () {

    const toggleClosedBtn = document.getElementById('toggleClosedPeriods');
    const tableContainer = document.getElementById('period-table-container');

    // Función para solicitar el partial a Django vía AJAX
    function loadPeriods(page = 1) {
        if (!toggleClosedBtn || !tableContainer) return;

        const showClosed = toggleClosedBtn.checked;
        const url = `${window.URLS.baseList}?show_closed=${showClosed}&page=${page}`;

        // Añadimos opacidad para indicar que está cargando
        tableContainer.style.opacity = '0.5';

        fetch(url, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(response => {
                if (!response.ok) throw new Error("Error en la petición al servidor");
                return response.json();
            })
            .then(data => {
                // Incrustamos el HTML puro
                tableContainer.innerHTML = data.html;
                tableContainer.style.opacity = '1';
            })
            .catch(error => {
                console.error('Error cargando la tabla:', error);
                tableContainer.style.opacity = '1';
            });
    }

    // Escuchador de eventos para el Toggle
    if (toggleClosedBtn) {
        toggleClosedBtn.addEventListener('change', () => loadPeriods(1));
    }

    // Exponemos la función de paginación al objeto window
    // para que los botones del partial puedan llamarla
    window.loadTablePage = function (pageNum) {
        loadPeriods(pageNum);
    };

});