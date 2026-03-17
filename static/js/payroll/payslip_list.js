// static/js/payroll/payslip_list.js
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchInput');
    const groupFilter = document.getElementById('groupFilter');
    const container = document.getElementById('payslip-table-container');

    // Inicializar controles de paginación: busca botones prev/next con atributo data-page
    function initPaginationControls(root) {
        const pagination = (root || document).querySelector('#js-pagination');
        if (!pagination) return;

        const firstBtn = pagination.querySelector('#btn-first');
        const prevBtn = pagination.querySelector('#btn-prev');
        const nextBtn = pagination.querySelector('#btn-next');
        const lastBtn = pagination.querySelector('#btn-last');
        const pageInput = pagination.querySelector('#page-input');

        const attach = (btn) => {
            if (!btn) return;
                    const page = btn.getAttribute('data-page');
                    btn.disabled = !page;
                    btn.removeEventListener('click', btn._payrollHandler);
                    btn._payrollHandler = function (e) {
                        e.preventDefault();
                        if (!page) return;
                        window.loadTablePage(Number(page));
                    };
                    btn.addEventListener('click', btn._payrollHandler);
        };

                    attach(firstBtn);
                    attach(prevBtn);
                    attach(nextBtn);
                    attach(lastBtn);

                    // Input: permitir escribir número de página
                    if (pageInput) {
                        const total = parseInt(pageInput.getAttribute('data-total') || '1', 10) || 1;
                        const submit = (v) => {
                            let p = parseInt(String(v).trim(), 10) || 1;
                            if (p < 1) p = 1;
                            if (p > total) p = total;
                            window.loadTablePage(p);
                        };
                        // Enter
                        pageInput.removeEventListener('keypress', pageInput._keyHandler);
                        pageInput._keyHandler = function (e) {
                            if (e.key === 'Enter') submit(e.target.value);
                        };
                        pageInput.addEventListener('keypress', pageInput._keyHandler);
                        // Blur (cuando sale del input)
                        pageInput.removeEventListener('blur', pageInput._blurHandler);
                        pageInput._blurHandler = function (e) {
                            submit(e.target.value);
                        };
                        pageInput.addEventListener('blur', pageInput._blurHandler);
                        // Validación rápida: evitar valores fuera de rango al cambiar
                        pageInput.removeEventListener('input', pageInput._inputHandler);
                        pageInput._inputHandler = function (e) {
                            const val = e.target.value.replace(/[^0-9]/g, '');
                            e.target.value = val;
                        };
                        pageInput.addEventListener('input', pageInput._inputHandler);
                    }
    }

    function performSearch(options) {
        options = options || {};
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

        // Página (para paginador server-side)
        if (options.page) paramsObj['page'] = options.page;
        // Si se pide full, solicitamos sin paginación al servidor
        if (options.full) paramsObj['full'] = '1';
        const params = new URLSearchParams(paramsObj);

        container.style.opacity = '0.5';

        return fetch(`${window.URLS.baseList}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                container.innerHTML = data.html;
                // Re-inicializar TableManager si existe en el HTML inyectado
                const table = container.querySelector('.managed-table');
                if (table && typeof TableManager !== 'undefined') {
                    new TableManager(table);
                    // Si pedimos la carga completa (full), asegurarnos de que
                    // TableManager tenga todas las filas en originalRows/currentRows
                    try {
                        const tm = table._tableManager;
                        if (options && options.full && tm) {
                            const tbody = table.tBodies && table.tBodies[0];
                            const allRows = tbody ? Array.from(tbody.rows) : Array.from(table.querySelectorAll('tbody tr'));
                            tm.originalRows = allRows.slice();
                            tm.currentRows = allRows.slice();
                            if (typeof tm.render === 'function') tm.render();
                        }
                    } catch (e) {
                        // No bloquear la UI por fallos en sincronización
                        console.warn('TableManager re-sync falló:', e);
                    }
                }
                // Inicializar controles de paginación si el partial los incluyó
                initPaginationControls(container);
                // Actualizar totales en la cabecera si vienen en la respuesta
                // Funciones de formato (puntos de miles y coma decimal)
                function formatNumberES(value) {
                    const parts = parseFloat(value || 0).toFixed(2).split('.');
                    const intPart = parts[0];
                    const decPart = parts[1];
                    return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + ',' + decPart;
                }
                function formatIntegerES(value) {
                    const n = parseInt(value || 0, 10) || 0;
                    return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
                }

                if (data.total_roles !== undefined) {
                    const el = document.getElementById('total-roles');
                    if (el) el.innerText = formatIntegerES(data.total_roles);
                }
                if (data.total_liquidado !== undefined) {
                    const el2 = document.getElementById('total-liquidado');
                    if (el2) el2.innerText = `$ ${formatNumberES(data.total_liquidado)}`;
                }
                container.style.opacity = '1';
                return Promise.resolve();
            })
            .catch(err => {
                console.error("Error en la petición:", err);
                container.style.opacity = '1';
                return Promise.reject(err);
            });
    }

    // Buscar con Enter: el botón de buscar fue eliminado, la búsqueda se dispara al presionar Enter
    if (groupFilter) groupFilter.addEventListener('change', performSearch);

    // Debounce helper
    function debounce(fn, wait) {
        let t;
        return function(...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), wait);
        };
    }

    // Flag para indicar que ya cargamos el dataset completo (full) en el cliente
    let fullLoaded = false;

    if (searchInput) {
        // Enter: búsqueda en servidor (paginada)
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                // Forzar recarga paginada y resetear estado fullLoaded
                fullLoaded = false;
                performSearch({page: 1});
            }
        });

        // Typing: cargar dataset completo la primera vez (debounced), luego dejar que TableManager filtre localmente
        const loadFullOnce = debounce(function () {
            if (fullLoaded) return;
            const q = (searchInput.value || '').trim();
            if (!q) return;
            performSearch({page: 1, full: true}).then(() => {
                fullLoaded = true;
            }).catch(() => {});
        }, 300);

        searchInput.addEventListener('input', function (e) {
            if (fullLoaded) return;
            loadFullOnce();
        });
    }

    // Exponer para que otras funciones globales (onchange inline) puedan invocarla
    window.performSearch = performSearch;
    // Permitir paginación AJAX desde los botones prev/next renderizados en el partial
    window.loadTablePage = function (page) {
        performSearch({page: page});
    };
    // Inicializar TableManager si está disponible (para la carga inicial de la página)
    const initialTable = document.querySelector('.managed-table');
    if (initialTable && typeof TableManager !== 'undefined') {
        new TableManager(initialTable);
    }

    // Inicializar paginación en carga inicial si el template ya la renderizó
    initPaginationControls(container);
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

