// static/js/payroll_period_list.js

document.addEventListener("DOMContentLoaded", function () {

    const toggleClosedBtn = document.getElementById('toggleClosedPeriods');
    const tableContainer = document.getElementById('period-table-container');

    // Función para solicitar el partial a Django vía AJAX
    function loadPeriods(page = 1) {
        if (!toggleClosedBtn || !tableContainer) return;

        // CAPTURAMOS EL ESTADO DEL CHECKBOX
        const showClosed = toggleClosedBtn.checked;

        // ARMAMOS LA URL CON EL FILTRO show_closed
        const url = `${window.URLS.baseList}?show_closed=${showClosed}&page=${page}`;

        tableContainer.style.opacity = '0.5';

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(response => {
                if (!response.ok) throw new Error("Error en la petición al servidor");
                return response.json();
            })
            .then(data => {
                tableContainer.innerHTML = data.html;
                tableContainer.style.opacity = '1';

                // Re-inicializamos el TableManager para que el buscador y el orden sigan funcionando
                try {
                    const newTable = tableContainer.querySelector('.managed-table');
                    if (newTable) {
                        if (newTable._tableManager) {
                            newTable._tableManager.originalRows = Array.from(newTable.querySelectorAll('tbody tr'));
                            newTable._tableManager.currentRows = [...newTable._tableManager.originalRows];
                            if (typeof newTable._tableManager.render === 'function') newTable._tableManager.render();
                        } else {
                            new TableManager(newTable);
                        }
                    }
                } catch (e) {
                    console.warn('Error inicializando TableManager tras inyección:', e);
                }
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