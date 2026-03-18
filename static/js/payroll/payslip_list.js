// static/js/payroll/payslip_list.js
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchInput');
    const groupFilter = document.getElementById('groupFilter');
    const container = document.getElementById('payslip-table-container');
    let currentPeriodId = window.CURRENT_PERIOD_ID;
    if (!currentPeriodId || currentPeriodId === "" || currentPeriodId === "None") {
        currentPeriodId = new URLSearchParams(window.location.search).get('period_id') || 'default';
    }

    const STORAGE_Q = 'payslip_q';
    const STORAGE_PAGE = 'payslip_page';
    const navEntries = performance.getEntriesByType("navigation");
   if (navEntries.length > 0 && navEntries[0].type !== "reload") {
        sessionStorage.removeItem(STORAGE_Q);
        sessionStorage.removeItem(STORAGE_PAGE);
    }
    const STORAGE_PERIOD = 'payslip_period';

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

        // Evitar parpadeo de layout: fijar altura mínima del contenedor mientras actualizamos
        try {
            const prevHeight = container.offsetHeight;
            container.style.minHeight = prevHeight + 'px';
        } catch (e) { /* ignore */
        }
        container.style.opacity = '0.5';

        return fetch(`${window.URLS.baseList}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                // Guardar scroll para restaurarlo después de la actualización
                const scrollTop = container.scrollTop;
                const scrollLeft = container.scrollLeft;
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
                // Persistir búsqueda y página para restaurar después (por ejemplo al cerrar modales)
                try {
                    sessionStorage.setItem(STORAGE_Q, paramsObj.q || '');
                    sessionStorage.setItem(STORAGE_PAGE, String(paramsObj.page || 1));
                    // Guardar el periodo actual asociado a la búsqueda
                    if (periodId) sessionStorage.setItem(STORAGE_PERIOD, String(periodId));
                } catch (e) {/* ignore */
                }

                // Restaurar scroll y quitar altura fija
                try {
                    container.scrollTop = scrollTop;
                    container.scrollLeft = scrollLeft;
                } catch (e) {
                }
                container.style.opacity = '1';
                try {
                    container.style.minHeight = '';
                } catch (e) {
                }
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
        return function (...args) {
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
            }).catch(() => {
            });
        }, 300);

        searchInput.addEventListener('input', function (e) {
            if (fullLoaded) return;
            loadFullOnce();
        });
    }

    // Restaurar búsqueda/página desde sessionStorage si existe
    try {
        // Resolver periodo actual (misma lógica que performSearch)
        let currentPeriod = window.CURRENT_PERIOD_ID;
        if (!currentPeriod || currentPeriod === "" || currentPeriod === "None") {
            const urlParams = new URLSearchParams(window.location.search);
            currentPeriod = urlParams.get('period_id');
        }

        const storedPeriod = sessionStorage.getItem(STORAGE_PERIOD);

        // Si hay un periodo almacenado y es distinto al actual, limpiar la búsqueda guardada
        if (storedPeriod && currentPeriod && String(storedPeriod) !== String(currentPeriod)) {
            try {
                sessionStorage.removeItem(STORAGE_Q);
                sessionStorage.removeItem(STORAGE_PAGE);
                sessionStorage.removeItem(STORAGE_PERIOD);
            } catch (e) { /* ignore */
            }
        } else {
            const storedQ = sessionStorage.getItem(STORAGE_Q);
            const storedPage = parseInt(sessionStorage.getItem(STORAGE_PAGE) || '1', 10) || 1;
            if (storedQ && storedQ.trim() !== '') {
                if (searchInput) searchInput.value = storedQ;
                // Realizar búsqueda paginada con la página almacenada
                performSearch({page: storedPage});
            }
        }
    } catch (e) {/* ignore */
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

    // Handler para el botón Recalcular Roles
    const btnRecalc = document.getElementById('btn-recalculate');
    if (btnRecalc) {
        btnRecalc.addEventListener('click', function () {
            const checkbox = document.getElementById('toggleWithheld');
            const show_withheld = checkbox && checkbox.checked ? 'only' : 'exclude';
            const periodId = window.CURRENT_PERIOD_ID || new URLSearchParams(window.location.search).get('period_id');
            if (!periodId) return alert('Periodo no seleccionado.');

            const form = new FormData();
            form.append('period_id', periodId);
            form.append('q', searchInput ? searchInput.value : '');
            form.append('group', groupFilter ? groupFilter.value : '');
            form.append('show_withheld', show_withheld);

            // Control que indica si el proceso fue cancelado por el usuario
            let stopped = false;

            // UI: mostrar modal con spinner moderno (SweetAlert si está disponible)
            function openProgressModal() {
                const html = `
                    <div class="recalc-progress-wrapper">
                        <div class="recalc-spinner-wrapper">
                            <div class="recalc-spinner" aria-hidden="true"></div>
                            <div>
                                <div class="recalc-progress-msg" id="recalc-progress-msg">Calculando, Por favor espere</div>
                            </div>
                        </div>
                
                    </div>`;
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        title: '',
                        html: html,
                        showConfirmButton: false,
                        showCancelButton: true,
                        cancelButtonText: 'Cancelar',
                        allowOutsideClick: false,
                        customClass: {popup: 'swal2-recalc-popup'},
                        didOpen: () => {
                            // Vincular Cancelar para detener polling
                            try {
                                const btn = document.querySelector('.swal2-cancel');
                                if (btn) {
                                    btn.addEventListener('click', function () {
                                        stopped = true;
                                        try {
                                            Swal.close();
                                        } catch (e) {
                                        }
                                    });
                                    btn.style.minWidth = '120px';
                                }
                            } catch (e) { /* ignore */
                            }
                        }
                    });
                } else {
                    // fallback simple: append to body
                    const wrapper = document.createElement('div');
                    wrapper.id = 'recalc-progress-fallback';
                    wrapper.innerHTML = html;
                    document.body.appendChild(wrapper);
                }
            }

            function closeProgressModal() {
                if (typeof Swal !== 'undefined') {
                    try {
                        Swal.close();
                    } catch (e) {
                    }
                } else {
                    const el = document.getElementById('recalc-progress-fallback');
                    if (el) el.remove();
                }
            }

            function setProgress(pct, msg) {
                try {
                    const msgEl = document.getElementById('recalc-progress-msg');
                    if (msgEl) msgEl.innerText = msg || (pct ? `${Math.round(pct)}%` : 'Procesando...');
                } catch (e) {/* ignore */
                }
            }

            openProgressModal();

            // Start recalculation request
            fetch('/payroll/payslips/recalculate/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: form
            })
                .then(res => res.json())
                .then(data => {
                    if (!data) throw new Error('No response');

                    // If backend provides a task_id, poll for progress — show spinner and update message
                    if (data.task_id) {
                        const taskId = data.task_id;
                        const statusUrl = `/payroll/payslips/recalculate-status/?task_id=${encodeURIComponent(taskId)}`;
                        // stopped variable defined in outer scope will be used
                        let lastPct = 0;
                        let totalCount = (typeof data.total === 'number' && data.total > 0) ? data.total : (typeof data.total_count === 'number' && data.total_count > 0 ? data.total_count : null);
                        let lastProcessed = 0;

                        // No cancel button: modal is informational only

                        const poll = () => {
                            if (stopped) return;
                            fetch(statusUrl, {
                                headers: {'X-Requested-With': 'XMLHttpRequest'},
                                credentials: 'same-origin'
                            })
                                .then(r => r.json())
                                .then(s => {
                                    if (!s) return;
                                    if (typeof s.processed_count === 'number' && totalCount) {
                                        lastProcessed = s.processed_count;
                                        const pct = Math.min(100, (lastProcessed / totalCount) * 100);
                                        lastPct = pct;
                                        setProgress(lastPct, s.message || `${lastProcessed} / ${totalCount}`);
                                    } else if (typeof s.processed === 'number' && totalCount) {
                                        lastProcessed = s.processed;
                                        const pct = Math.min(100, (lastProcessed / totalCount) * 100);
                                        lastPct = pct;
                                        setProgress(lastPct, s.message || `${lastProcessed} / ${totalCount}`);
                                    } else {
                                        const pct = typeof s.progress !== 'undefined' ? Number(s.progress) : (s.done ? 100 : lastPct);
                                        lastPct = isNaN(pct) ? lastPct : pct;
                                        setProgress(lastPct, s.message || (s.done ? 'Completado' : 'Procesando...'));
                                    }

                                    if (s.done || (totalCount && lastProcessed >= totalCount) || (typeof s.progress !== 'undefined' && s.progress >= 100) || s.success) {
                                        stopped = true;
                                        closeProgressModal();
                                        setTimeout(() => {
                                            if (s.success || (!s.success && s.done && lastProcessed >= totalCount)) {
                                                try {
                                                    document.querySelectorAll('.swal2-cancel').forEach(el => el.remove());
                                                } catch (e) {
                                                }
                                                if (typeof Swal !== 'undefined') Swal.fire({
                                                    title: 'Recalculo completado',
                                                    text: `Se recalcularon ${s.count || data.count || totalCount || 0} roles.`,
                                                    icon: 'success',
                                                    confirmButtonText: 'OK',
                                                    showCancelButton: false
                                                });
                                                performSearch({page: 1});
                                            } else {
                                                try {
                                                    document.querySelectorAll('.swal2-cancel').forEach(el => el.remove());
                                                } catch (e) {
                                                }
                                                if (typeof Swal !== 'undefined') Swal.fire({
                                                    title: 'Error',
                                                    text: s.message || 'Error en recalculo',
                                                    icon: 'error',
                                                    confirmButtonText: 'OK',
                                                    showCancelButton: false
                                                });
                                            }
                                        }, 300);
                                    } else {
                                        setTimeout(poll, 900);
                                    }
                                })
                                .catch(err => {
                                    console.error('poll error', err);
                                    setTimeout(poll, 1500);
                                });
                        };

                        // seed UI
                        if (totalCount) {
                            setProgress(0, `0 / ${totalCount}`);
                        } else {
                            setProgress(5, 'Calculando, Por favor espere');
                        }
                        setTimeout(poll, 600);
                    } else if (data && data.success) {
                        // No task_id: server finished synchronously
                        closeProgressModal();
                        if (typeof Swal !== 'undefined') Swal.fire({
                            title: 'Recalculo completado',
                            text: `Se recalcularon ${data.count || 0} roles.`,
                            icon: 'success',
                            confirmButtonText: 'OK',
                            showCancelButton: false
                        });
                        performSearch({page: 1});
                    } else {
                        closeProgressModal();
                        if (typeof Swal !== 'undefined') Swal.fire({
                            title: 'Error',
                            text: data && data.message || 'Error',
                            icon: 'error',
                            confirmButtonText: 'OK',
                            showCancelButton: false
                        });
                    }
                })
                .catch(err => {
                    console.error('Error recalculando roles:', err);
                    closeProgressModal();
                    if (typeof Swal !== 'undefined') Swal.fire({
                        title: 'Error',
                        text: 'Fallo al recalcular roles',
                        icon: 'error',
                        confirmButtonText: 'OK',
                        showCancelButton: false
                    });
                });
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

