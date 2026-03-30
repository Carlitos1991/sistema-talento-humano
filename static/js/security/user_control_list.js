document.addEventListener('DOMContentLoaded', function () {
    const tableContainerId = 'user-control-table-container';
    const searchInputClass = '.table-search-input';

    // Inicializar TableManager para la tabla principal
    let tableManager = new TableManager(tableContainerId, {
        pagination: {
            itemsPerPage: 15,
            paginationContainerClass: '.pagination-container'
        }
    });

    // Manejador para la búsqueda
    const searchInput = document.querySelector(searchInputClass);
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            tableManager.search(this.value);
        });
    }
});
