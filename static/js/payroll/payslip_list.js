// static/js/payroll/payslip_list.js
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchInput');
    const groupFilter = document.getElementById('groupFilter');
    const container = document.getElementById('payslip-table-container');

    function performSearch(options) {
        // Magia: Si no lo halla en la variable, lo roba directamente de la URL
        let periodId = window.CURRENT_PERIOD_ID;
        if (!periodId || periodId === "" || periodId === "None") {
            const urlParams = new URLSearchParams(window.location.search);
            periodId = urlParams.get('period_id');
        }

        if (!periodId) {
            console.error("Error: ID de periodo no válido:", periodId);
            return;
        }

        const paramsObj = {
            period_id: periodId,
            q: searchInput ? searchInput.value : '',
            group: groupFilter ? groupFilter.value : ''
        };

        // Opciones adicionales (p.ej. mostrar retenidos)
        const checkbox = document.getElementById('toggleWithheld');
        const show_withheld_val = options && typeof options.show_withheld !== 'undefined'
            ? (options.show_withheld ? 'only' : 'exclude')
            : (checkbox && checkbox.checked ? 'only' : 'exclude');
        paramsObj['show_withheld'] = show_withheld_val;

        const params = new URLSearchParams(paramsObj);

        container.style.opacity = '0.5';

        fetch(`${window.URLS.baseList}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                container.innerHTML = data.html;
                // Re-inicializar TableManager si existe en el HTML inyectado
                const table = container.querySelector('.managed-table');
                if (table && typeof TableManager !== 'undefined') {
                    new TableManager(table);
                }
                // Actualizar totales en la cabecera si vienen en la respuesta
                if (data.total_roles !== undefined) {
                    const el = document.getElementById('total-roles');
                    if (el) el.innerText = data.total_roles;
                }
                if (data.total_liquidado !== undefined) {
                    const el2 = document.getElementById('total-liquidado');
                    if (el2) el2.innerText = `$ ${parseFloat(data.total_liquidado).toFixed(2)}`;
                }
                container.style.opacity = '1';
            })
            .catch(err => {
                console.error("Error en la petición:", err);
                container.style.opacity = '1';
            });
    }

    // Buscar con Enter: el botón de buscar fue eliminado, la búsqueda se dispara al presionar Enter
    if (groupFilter) groupFilter.addEventListener('change', performSearch);

    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') performSearch();
        });
    }

    // Exponer para que otras funciones globales (onchange inline) puedan invocarla
    window.performSearch = performSearch;
});

function downloadFilteredReport(type) {
    const searchInput = document.getElementById('searchInput');
    const groupFilter = document.getElementById('groupFilter');

    const q = searchInput ? searchInput.value : '';
    const group = groupFilter ? groupFilter.value : '';

    // Misma magia para la descarga de reportes
    let periodId = window.CURRENT_PERIOD_ID;
    if (!periodId || periodId === "" || periodId === "None") {
        periodId = new URLSearchParams(window.location.search).get('period_id');
    }

    if (!periodId) {
        alert("Error: No se pudo identificar el periodo. Regrese a la lista e intente de nuevo.");
        return;
    }

    const reportPath = type === 'banco' ? 'bank' : 'grouped';
    const checkbox = document.getElementById('toggleWithheld');
    const show_withheld = checkbox && checkbox.checked ? 'only' : 'exclude';
    const url = `/payroll/reports/${reportPath}/${periodId}/?q=${encodeURIComponent(q)}&group=${encodeURIComponent(group)}&filtro=NORMAL&show_withheld=${show_withheld}`;
    window.open(url, '_blank');
}

// Función expuesta para el checkbox del template
function performSearchWithOptions() {
    const checkbox = document.getElementById('toggleWithheld');
    performSearch({show_withheld: checkbox && checkbox.checked});
}

// Inicializar TableManager si está disponible (para la carga inicial de la página)
document.addEventListener('DOMContentLoaded', function () {
    const initialTable = document.querySelector('.managed-table');
    if (initialTable && typeof TableManager !== 'undefined') {
        new TableManager(initialTable);
    }
});