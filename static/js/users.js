document.addEventListener('DOMContentLoaded', () => {

    // --- VARIABLES ---
    const searchInput = document.getElementById('table-search');
    const tableContainer = document.getElementById('table-content-wrapper');
    let currentStatus = 'all'; // all, active, inactive

    // --- FUNCIÓN PRINCIPAL DE FETCH ---
    function fetchUsers(query = '', status = 'all') {
        // Construimos la URL con parámetros
        const url = new URL(window.location.href);
        url.searchParams.set('q', query);
        if (status !== 'all') {
            url.searchParams.set('status', status);
        } else {
            url.searchParams.delete('status');
        }

        fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
        .then(response => response.text())
        .then(html => {
            if (tableContainer) {
                tableContainer.innerHTML = html;
            }
        })
        .catch(err => console.error("Error cargando usuarios:", err));
    }

    // --- BUSCADOR CON DEBOUNCE ---
    function debounce(func, timeout = 300) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => { func.apply(this, args); }, timeout);
        };
    }

    if (searchInput) {
        searchInput.addEventListener('input', debounce((e) => {
            fetchUsers(e.target.value, currentStatus);
        }, 500));
    }

    // --- FILTRADO POR ESTADO (TARJETAS) ---
    // Esta función se llama desde el HTML con onclick="filterByStatus(...)"
    window.filterByStatus = function(status) {
        currentStatus = status;

        // 1. Efecto visual en las tarjetas (Opacidad)
        const cards = {
            'all': document.getElementById('card-filter-all'),
            'active': document.getElementById('card-filter-active'),
            'inactive': document.getElementById('card-filter-inactive')
        };

        // Reset visual
        Object.values(cards).forEach(c => { if(c) c.classList.add('opacity-low') });

        // Activar la seleccionada
        if(cards[status]) cards[status].classList.remove('opacity-low');

        // 2. Cargar datos
        const query = searchInput ? searchInput.value : '';
        fetchUsers(query, status);
    };

});