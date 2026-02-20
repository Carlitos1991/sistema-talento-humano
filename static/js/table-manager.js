/* static/js/table-manager.js */

class TableManager {
    constructor(tableElement) {
        this.table = tableElement;
        this.tbody = this.table.querySelector('tbody');
        this.originalRows = Array.from(this.tbody.querySelectorAll('tr'));
        this.currentRows = [...this.originalRows];

        this.pageSize = parseInt(this.table.dataset.pageSize) || 10;
        this.currentPage = 1;
        this.sortCol = null;
        this.sortAsc = true;

        this.wrapper = this.table.closest('.content-table') || this.table.parentElement;
        this.searchInput = this.wrapper.querySelector('.table-search-input');

        // Inicializar
        this.initSortHeaders();
        this.initSearch();
        this.initPagination();
        this.updateStats(); // Stats iniciales
        this.render();

        this.table._tableManager = this;
    }

    /* ... (initSortHeaders y handleSort se mantienen igual que la versión anterior) ... */
    initSortHeaders() {
        const headers = this.table.querySelectorAll('thead th');
        headers.forEach((th, index) => {
            if (th.classList.contains('no-sort')) return;
            th.classList.add('sortable-header');
            if (!th.querySelector('.sort-arrow')) th.innerHTML += ' <span class="sort-arrow">⇅</span>';
            th.addEventListener('click', () => this.handleSort(index, th, headers));
        });
    }

    handleSort(colIndex, clickedTh, allHeaders) {
        if (this.sortCol === colIndex) {
            this.sortAsc = !this.sortAsc;
        } else {
            this.sortCol = colIndex;
            this.sortAsc = true;
            allHeaders.forEach(h => {
                h.classList.remove('sorted-asc', 'sorted-desc');
                const arrow = h.querySelector('.sort-arrow');
                if (arrow) arrow.innerText = '⇅';
            });
        }
        clickedTh.classList.remove('sorted-asc', 'sorted-desc');
        clickedTh.classList.add(this.sortAsc ? 'sorted-asc' : 'sorted-desc');
        const arrow = clickedTh.querySelector('.sort-arrow');
        if (arrow) arrow.innerText = this.sortAsc ? '↑' : '↓';

        this.sortData();
        this.render();
    }

    sortData() {
        if (this.sortCol === null) return;
        this.currentRows.sort((rowA, rowB) => {
            const cellA = rowA.children[this.sortCol]?.innerText.trim() || '';
            const cellB = rowB.children[this.sortCol]?.innerText.trim() || '';
            const numA = parseFloat(cellA.replace(/[^0-9.-]+/g, ""));
            const numB = parseFloat(cellB.replace(/[^0-9.-]+/g, ""));
            const isNum = !isNaN(numA) && !isNaN(numB) && cellA !== '' && cellB !== '';

            let comparison = isNum ? numA - numB : cellA.localeCompare(cellB);
            return this.sortAsc ? comparison : -comparison;
        });
    }

    initSearch() {
        if (!this.searchInput) return;
        this.searchInput.addEventListener('input', (e) => {
            this.filterByText(e.target.value);
        });
    }

    filterByText(term) {
        term = term.toLowerCase();
        this.currentPage = 1;
        if (!term) {
            this.currentRows = [...this.originalRows];
        } else {
            this.currentRows = this.originalRows.filter(row => row.innerText.toLowerCase().includes(term));
        }
        if (this.sortCol !== null) this.sortData();
        this.render();
    }

    /* Método para filtros externos (Como los Cards de Levels) */
    filterByColumnData(dataAttribute, value) {
        this.currentPage = 1;
        if (value === 'all') {
            this.currentRows = [...this.originalRows];
        } else {
            this.currentRows = this.originalRows.filter(row => {
                return row.getAttribute(`data-${dataAttribute}`) === value;
            });
        }
        // Reaplicar búsqueda de texto si existe
        if (this.searchInput && this.searchInput.value) {
            const term = this.searchInput.value.toLowerCase();
            this.currentRows = this.currentRows.filter(row => row.innerText.toLowerCase().includes(term));
        }

        if (this.sortCol !== null) this.sortData();
        this.render();
    }

    updateStats() {
        // Actualiza contadores visuales si existen en el DOM
        const elTotal = document.getElementById('stat-total');
        if (elTotal) elTotal.innerText = this.originalRows.length; // Total absoluto

        // Para activos/inactivos, miramos el data-status de las filas originales
        const elActive = document.getElementById('stat-active');
        const elInactive = document.getElementById('stat-inactive');

        if (elActive || elInactive) {
            const active = this.originalRows.filter(r => r.dataset.status === 'true').length;
            const inactive = this.originalRows.filter(r => r.dataset.status === 'false').length;
            if (elActive) elActive.innerText = active;
            if (elInactive) elInactive.innerText = inactive;
        }
    }

    initPagination() {
        let pagContainer = this.wrapper.querySelector('.pagination-container');
        if (!pagContainer) {
            pagContainer = document.createElement('div');
            pagContainer.className = 'pagination-container';
            this.table.parentNode.insertBefore(pagContainer, this.table.nextSibling);
        }
        this.pagContainer = pagContainer;
    }

    renderPaginationControls(totalPages) {
        if (totalPages <= 1 && this.currentRows.length > 0) {
            this.pagContainer.style.display = 'none';
            return;
        }
        this.pagContainer.style.display = 'flex';

        this.pagContainer.innerHTML = `
            <div class="pagination-info">
                Mostrando ${(this.currentPage - 1) * this.pageSize + 1}-${Math.min(this.currentPage * this.pageSize, this.currentRows.length)} de ${this.currentRows.length}
            </div>
            <div class="pagination-controls">
                <button class="page-btn btn-first" title="Primera"><i class="fas fa-angle-double-left"></i></button>
                <button class="page-btn btn-prev" title="Anterior"><i class="fas fa-angle-left"></i></button>
                
                <div class="page-input-wrapper">
                    <input type="number" class="page-input" value="${this.currentPage}" min="1" max="${totalPages}">
                </div>

                <button class="page-btn btn-next" title="Siguiente"><i class="fas fa-angle-right"></i></button>
                <button class="page-btn btn-last" title="Última"><i class="fas fa-angle-double-right"></i></button>
            </div>
        `;

        const input = this.pagContainer.querySelector('.page-input');
        const go = (page) => {
            if (page < 1) page = 1;
            if (page > totalPages) page = totalPages;
            this.currentPage = page;
            this.render();
        };

        this.pagContainer.querySelector('.btn-first').onclick = () => go(1);
        this.pagContainer.querySelector('.btn-prev').onclick = () => go(this.currentPage - 1);
        this.pagContainer.querySelector('.btn-next').onclick = () => go(this.currentPage + 1);
        this.pagContainer.querySelector('.btn-last').onclick = () => go(totalPages);

        // Manejo del Input
        input.addEventListener('change', () => go(parseInt(input.value)));
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') go(parseInt(input.value));
        });

        // Estado de botones
        this.pagContainer.querySelector('.btn-first').disabled = (this.currentPage === 1);
        this.pagContainer.querySelector('.btn-prev').disabled = (this.currentPage === 1);
        this.pagContainer.querySelector('.btn-next').disabled = (this.currentPage === totalPages);
        this.pagContainer.querySelector('.btn-last').disabled = (this.currentPage === totalPages);
    }

    render() {
        this.updateStats(); // Actualizar stats

        const totalRows = this.currentRows.length;
        const totalPages = Math.ceil(totalRows / this.pageSize) || 1;
        if (this.currentPage > totalPages) this.currentPage = totalPages;
        if (this.currentPage < 1) this.currentPage = 1;

        const start = (this.currentPage - 1) * this.pageSize;
        const end = start + this.pageSize;

        this.tbody.innerHTML = '';

        if (totalRows > 0) {
            this.currentRows.slice(start, end).forEach(row => {
                row.style.display = '';
                this.tbody.appendChild(row);
            });
        } else {
            const emptyRow = document.createElement('tr');
            emptyRow.innerHTML = `<td colspan="100%" style="text-align:center; padding:30px; color:#94a3b8;">Sin resultados</td>`;
            this.tbody.appendChild(emptyRow);
        }

        this.renderPaginationControls(totalPages);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.managed-table').forEach(t => new TableManager(t));
});