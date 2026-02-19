// JS global para ordenamiento de tablas
// Aplica a todas las tablas con la clase .sortable-table

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.sortable-table').forEach(function (table) {
        const headers = table.querySelectorAll('th');
        headers.forEach(function (th, colIdx) {
            th.style.cursor = 'pointer';
            th.innerHTML += ' <span class="sort-arrow">⇅</span>';
            th.addEventListener('click', function () {
                // Ordenar todas las filas filtradas (no solo las visibles)
                // Ordenar sobre el filtro actual
                if (window.filteredRows && window.filteredRows.length > 0) {
                    console.log('Sort triggered:', { colIdx, filteredRows: window.filteredRows.length });
                    const asc = th.classList.toggle('sorted-asc');
                    th.classList.remove('sorted-desc');
                    headers.forEach(h => {
                        if (h !== th) h.classList.remove('sorted-asc', 'sorted-desc');
                    });
                    if (!asc) th.classList.add('sorted-desc');
                    window.currentSortCol = colIdx;
                    window.currentSortAsc = asc;
                    if (window.renderTable) window.renderTable();
                }
            });
        });
    });
});

// CSS sugerido para flechas
// .sort-arrow { font-size: 0.9em; color: #888; }
// th.sorted-asc .sort-arrow { color: #1e293b; content: "↑"; }
// th.sorted-desc .sort-arrow { color: #1e293b; content: "↓"; }
