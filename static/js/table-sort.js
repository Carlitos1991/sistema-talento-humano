// JS global para ordenamiento de tablas
// Aplica a todas las tablas con la clase .sortable-table

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.sortable-table').forEach(function (table) {
        const headers = table.querySelectorAll('th');
        headers.forEach(function (th, colIdx) {
            th.style.cursor = 'pointer';
            th.innerHTML += ' <span class="sort-arrow">⇅</span>';
            th.addEventListener('click', function () {
                const rows = Array.from(table.querySelectorAll('tbody tr')).filter(r => r.parentNode === table.querySelector('tbody'));
                const asc = th.classList.toggle('sorted-asc');
                th.classList.remove('sorted-desc');
                headers.forEach(h => {
                    if (h !== th) h.classList.remove('sorted-asc', 'sorted-desc');
                });
                if (!asc) th.classList.add('sorted-desc');
                // Ordenar
                rows.sort(function (a, b) {
                    let cellA = a.children[colIdx].innerText.trim();
                    let cellB = b.children[colIdx].innerText.trim();
                    // Detectar número
                    if (!isNaN(cellA) && !isNaN(cellB)) {
                        cellA = parseFloat(cellA);
                        cellB = parseFloat(cellB);
                    }
                    if (asc) {
                        return cellA > cellB ? 1 : cellA < cellB ? -1 : 0;
                    } else {
                        return cellA < cellB ? 1 : cellA > cellB ? -1 : 0;
                    }
                });
                // Reinsertar filas ordenadas
                const tbody = table.querySelector('tbody');
                rows.forEach(row => tbody.appendChild(row));
            });
        });
    });
});

// CSS sugerido para flechas
// .sort-arrow { font-size: 0.9em; color: #888; }
// th.sorted-asc .sort-arrow { color: #1e293b; content: "↑"; }
// th.sorted-desc .sort-arrow { color: #1e293b; content: "↓"; }
