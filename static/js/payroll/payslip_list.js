// static/js/payroll/payslip_list.js
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchInput');
    const btnSearch = document.getElementById('btnSearch');
    const groupFilter = document.getElementById('groupFilter');
    const container = document.getElementById('payslip-table-container');

    function performSearch() {
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

        const params = new URLSearchParams({
            period_id: periodId,
            q: searchInput ? searchInput.value : '',
            group: groupFilter ? groupFilter.value : ''
        });

        container.style.opacity = '0.5';

        fetch(`${window.URLS.baseList}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                container.innerHTML = data.html;
                container.style.opacity = '1';
            })
            .catch(err => {
                console.error("Error en la petición:", err);
                container.style.opacity = '1';
            });
    }

    if (btnSearch) btnSearch.addEventListener('click', performSearch);
    if (groupFilter) groupFilter.addEventListener('change', performSearch);

    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') performSearch();
        });
    }
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
    const url = `/payroll/reports/${reportPath}/${periodId}/?q=${encodeURIComponent(q)}&group=${encodeURIComponent(group)}&filtro=NORMAL`;
    window.open(url, '_blank');
}