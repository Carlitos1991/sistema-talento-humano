/**
 * LÓGICA ESPECÍFICA DE NIVELES
 */

window.toggleInactiveLevels = function (isChecked) {
    // 1. Obtenemos la URL actual y añadimos el parámetro
    const url = new URL(window.location.href);
    url.searchParams.set('show_inactive', isChecked);

    // 2. Pedimos a Django el HTML de la tabla filtrada vía AJAX
    fetch(url, {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(res => res.json())
        .then(data => {
            // 3. Reemplazamos el contenido de la tabla
            const wrapper = document.getElementById('table-content-wrapper');
            if (wrapper) {
                wrapper.innerHTML = data.html;

                // Reinicializar TableManager si existe en tu sistema
                if (typeof TableManager !== 'undefined') {
                    const table = wrapper.querySelector('.managed-table');
                    if (table) new TableManager(table);
                }
            }
        })
        .catch(err => console.error("Error filtrando niveles:", err));
};
