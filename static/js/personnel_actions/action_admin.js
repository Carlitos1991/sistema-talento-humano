/**
 * action_admin.js
 *
 * ARQUITECTURA CLAVE:
 *   window.fetchTableData se define ANTES del DOMContentLoaded para que
 *   los onclick inline del partial HTML siempre la encuentren, tanto en
 *   la carga inicial como después de cada reemplazo AJAX.
 */

// ─── Estado global accesible por los onclick del partial ───────────────────
window._paState = {
    currentPage: 1,
    totalPages: 1,
    currentOrder: null,
    currentDirection: 'asc',
};

/**
 * window.fetchPeople — alias requerido por TableManager cuando
 * externalPagination=true. El TableManager guarda el sort en
 * window._personExport.sort y luego llama a esta función.
 */
window.fetchPeople = function (page) {
    window.fetchTableData(page || 1);
};

/**
 * Recarga la tabla vía AJAX.
 * Expuesta globalmente para los onclick del partial HTML.
 */
window.fetchTableData = function (page) {
    var state = window._paState;
    var container = document.getElementById('table-content-wrapper');
    var urlList = document.getElementById('url-list');
    var filtersForm = document.getElementById('filtersForm');

    if (!container || !urlList) return;

    var pageNumber = (page != null) ? parseInt(page, 10) : state.currentPage;

    var params = new URLSearchParams();
    params.set('page', pageNumber);

    if (filtersForm) {
        new FormData(filtersForm).forEach(function (v, k) {
            if (v && v.toString().trim()) params.set(k, v);
        });
    }

    // Leer orden desde TableManager (guarda en window._personExport.sort)
    var sortInfo = window._personExport && window._personExport.sort;
    if (sortInfo && sortInfo.field) {
        params.set('order_by', sortInfo.field);
        params.set('direction', sortInfo.asc ? 'asc' : 'desc');
    } else if (state.currentOrder) {
        params.set('order_by', state.currentOrder);
        params.set('direction', state.currentDirection);
    }

    fetch(urlList.value + '?' + params.toString(), {
        headers: {'X-Requested-With': 'XMLHttpRequest'}
    })
        .then(function (res) {
            return res.json();
        })
        .then(function (data) {
            if (data.html) {
                container.innerHTML = data.html;
                // Re-inicializar TableManager en la tabla recién inyectada
                var newTable = container.querySelector('.managed-table');
                if (newTable && window.TableManager) {
                    new window.TableManager(newTable);
                }

                // Aplicar estado visual del sort a los headers
                var ths = container.querySelectorAll('thead th');
                ths.forEach(function (th) {
                    th.classList.remove('sorted-asc', 'sorted-desc');
                    var link = th.querySelector('.sortable');
                    if (link && link.dataset.order === state.currentOrder) {
                        th.classList.add(state.currentDirection === 'asc' ? 'sorted-asc' : 'sorted-desc');
                        var arrow = th.querySelector('.sort-arrow');
                        if (arrow) arrow.innerText = state.currentDirection === 'asc' ? '↑' : '↓';
                    } else {
                        var arrow = th.querySelector('.sort-arrow');
                        if (arrow) arrow.innerText = '⇅';
                    }
                });

                // Re-inicializar búsqueda rápida después de cargar nuevos datos
                if (window.applyPersonnelActionClientSearchFilter) {
                    window.applyPersonnelActionClientSearchFilter();
                }
            }
            state.currentPage = data.page_number || 1;
            state.totalPages = data.num_pages || 1;
        })
        .catch(function (err) {
            console.error('fetchTableData error:', err);
        });
};

// ─── Inicialización al cargar el DOM ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {

    var state = window._paState;

    // Leer paginación inicial inyectada por Django
    if (window.initialPagination) {
        state.currentPage = window.initialPagination.current_page || 1;
        state.totalPages = window.initialPagination.total_pages || 1;
    }

    var csrfToken = (document.getElementById('csrf-token') || {}).value || '';
    var tableContainer = document.getElementById('table-content-wrapper');
    var filtersForm = document.getElementById('filtersForm');
    var detailModal = document.getElementById('actionDetailModal');
    var detailContent = document.getElementById('modal-detail-content');

    // ── BÚSQUEDA RÁPIDA (Client-side filtering) ────────────────────────
    var initQuickSearch = function () {
        var filterNameInput = document.getElementById('filter_name');
        if (!filterNameInput) return;

        var normalizeSearchText = function (value) {
            return (value || '')
                .toString()
                .toLowerCase()
                .normalize('NFD')
                .replace(/[\u0300-\u036f]/g, '')
                .trim();
        };

        var filterVisibleRows = function () {
            var terms = normalizeSearchText(filterNameInput.value)
                .split(/\s+/)
                .filter(Boolean);

            if (!tableContainer) return;

            var dataRows = Array.from(tableContainer.querySelectorAll('tbody tr[data-search-text]'));
            var visibleRows = 0;

            dataRows.forEach(function (row) {
                var rowText = normalizeSearchText(row.dataset.searchText || row.textContent || '');
                var matches = terms.length === 0 || terms.every(function (term) {
                    return rowText.includes(term);
                });
                row.style.display = matches ? '' : 'none';
                if (matches) visibleRows += 1;
            });

            var noResultsRow = tableContainer.querySelector('#client-no-results');
            if (noResultsRow) {
                noResultsRow.style.display = dataRows.length > 0 && visibleRows === 0 ? '' : 'none';
            }
        };

        // Exponer para reutilizar después de renderizados AJAX
        window.applyPersonnelActionClientSearchFilter = filterVisibleRows;

        // Debounce para búsqueda en el backend
        var searchTimeout;
        filterNameInput.addEventListener('input', function () {
            filterVisibleRows();
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(function () {
                var term = filterNameInput.value.trim();
                if (term) {
                    state.currentPage = 1;
                    window.fetchTableData(1);
                }
            }, 500);
        });

        // Presionar Enter para buscar inmediatamente
        filterNameInput.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                filterVisibleRows();
                clearTimeout(searchTimeout);
                var term = filterNameInput.value.trim();
                state.currentPage = 1;
                window.fetchTableData(1);
            }
        });

        // Initial filter on first load
        filterVisibleRows();
    };

    // ── Filtros: Buscar / Limpiar ─────────────────────────────────────────
    var btnSearch = document.getElementById('btn-filter-search');
    var btnClear = document.getElementById('btn-filter-clear');
    var filterActionType = document.getElementById('filter_action_type');

    // Event listener para cambios en Tipo de Acción
    if (filterActionType) {
        filterActionType.addEventListener('change', function () {
            state.currentPage = 1;
            window.fetchTableData(1);
        });
    }

    if (btnSearch) {
        btnSearch.addEventListener('click', function (e) {
            e.preventDefault();
            state.currentPage = 1;
            window.fetchTableData(1);
        });
    }
    if (btnClear && filtersForm) {
        btnClear.addEventListener('click', function (e) {
            e.preventDefault();
            filtersForm.reset();
            var filterNameInput = document.getElementById('filter_name');
            if (filterNameInput) filterNameInput.value = '';
            if (filterActionType) {
                filterActionType.value = '';
            }
            state.currentPage = 1;
            window.fetchTableData(1);
        });
    }

    // Event listeners para campos de fecha
    var filterDateFrom = document.getElementById('filter_date_from');
    var filterDateTo = document.getElementById('filter_date_to');
    if (filterDateFrom) {
        filterDateFrom.addEventListener('change', function () {
            state.currentPage = 1;
            window.fetchTableData(1);
        });
    }
    if (filterDateTo) {
        filterDateTo.addEventListener('change', function () {
            state.currentPage = 1;
            window.fetchTableData(1);
        });
    }

    // Event listeners para campos de filtro de texto (Dirección y Cargo)
    var filterPrevUnit = document.getElementById('filter_prev_unit');
    var filterNewUnit = document.getElementById('filter_new_unit');
    var filterPrevPos = document.getElementById('filter_prev_pos');
    var filterNewPos = document.getElementById('filter_new_pos');

    var onFilterTextChange = function () {
        state.currentPage = 1;
        window.fetchTableData(1);
    };

    if (filterPrevUnit) {
        filterPrevUnit.addEventListener('change', onFilterTextChange);
    }
    if (filterNewUnit) {
        filterNewUnit.addEventListener('change', onFilterTextChange);
    }
    if (filterPrevPos) {
        filterPrevPos.addEventListener('change', onFilterTextChange);
    }
    if (filterNewPos) {
        filterNewPos.addEventListener('change', onFilterTextChange);
    }

    // ── Cerrar modal de detalle ───────────────────────────────────────────
    if (detailModal) {
        detailModal.addEventListener('click', function (e) {
            if (e.target === detailModal ||
                e.target.closest('.js-close-detail-modal') ||
                e.target.closest('.btn-close-modal')) {
                _closeDetailModal();
            }
        });
    }

    // ── Delegación de clics en la tabla ──────────────────────────────────
    if (tableContainer) {
        tableContainer.addEventListener('click', function (e) {

            // A. VER DETALLE
            var detailBtn = e.target.closest('.js-view-detail');
            if (detailBtn) {
                e.preventDefault();
                _viewDetail(detailBtn.dataset.actionId);
                return;
            }

            // B. EDITAR ACCIÓN
            var editBtn = e.target.closest('.js-edit-action');
            if (editBtn) {
                e.preventDefault();
                _openEditModal(editBtn.dataset.actionId);
                return;
            }

            // C. REGISTRAR ACCIÓN
            var registerBtn = e.target.closest('.js-register-action');
            if (registerBtn) {
                e.preventDefault();
                _confirmRegister(registerBtn.dataset.actionId, csrfToken);
                return;
            }

            // D. IMPRIMIR PDF
            var printBtn = e.target.closest('.js-print-action');
            if (printBtn) {
                e.preventDefault();
                window.open('/personnel_actions/' + printBtn.dataset.actionId + '/pdf/', '_blank');
                return;
            }

            var inactivateBtn = e.target.closest('.js-inactivate-action');
            if (inactivateBtn) {
                e.preventDefault();
                _confirmInactivate(inactivateBtn.dataset.actionId, inactivateBtn.dataset.number, csrfToken);
                return;
            }
        });
    }

    // ── Ordenamiento por columna ──────────────────────────────────────────
    document.addEventListener('click', function (e) {
        var s = e.target.closest('.sortable');
        if (!s) return;
        e.preventDefault();
        var order = s.dataset.order;
        if (state.currentOrder === order) {
            state.currentDirection = (state.currentDirection === 'asc') ? 'desc' : 'asc';
        } else {
            state.currentOrder = order;
            state.currentDirection = 'asc';
        }
        state.currentPage = 1;
        window.fetchTableData(1);
    });

    // ── Exportar ──────────────────────────────────────────────────────────
    var btnExportExcel = document.getElementById('btn-export-excel');
    var btnExportPdf = document.getElementById('btn-export-pdf');

    // Función global para exportar a CSV
    window.exportTableToCSV = function (table) {
        var filename = (table && table.dataset.filename) || 'acciones_personal';
        var csv = [];
        var rows = table.querySelectorAll('tr');

        rows.forEach(function (row) {
            var cols = row.querySelectorAll('td, th');
            var rowData = [];
            cols.forEach(function (col) {
                rowData.push('"' + (col.innerText || '').replace(/"/g, '""') + '"');
            });
            csv.push(rowData.join(','));
        });

        var csvContent = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv.join('\n'));
        var link = document.createElement('a');
        link.setAttribute('href', csvContent);
        link.setAttribute('download', filename + '.csv');
        link.click();
    };

    // Función global para exportar a PDF
    window.exportTableToPDF = function (table) {
        var filename = (table && table.dataset.filename) || 'acciones_personal';
        var html = '<html><head><meta charset="utf-8"><title>' + filename + '</title>' +
            '<style>table{border-collapse:collapse;width:100%;} th,td{border:1px solid #ddd;padding:8px;text-align:left;} th{background-color:#f2f2f2;}</style>' +
            '</head><body>' + table.outerHTML + '</body></html>';
        var w = window.open('', '_blank');
        if (!w) {
            alert('Permita ventanas emergentes para exportar PDF');
            return;
        }
        w.document.write(html);
        w.document.close();
        w.focus();
        setTimeout(function () {
            w.print();
        }, 600);
    };

    if (btnExportExcel) {
        btnExportExcel.addEventListener('click', function (e) {
            e.preventDefault();
            var table = document.querySelector('.exportable-table');
            if (table) window.exportTableToCSV(table);
        });
    }
    if (btnExportPdf) {
        btnExportPdf.addEventListener('click', function (e) {
            e.preventDefault();
            var table = document.querySelector('.exportable-table');
            if (table) window.exportTableToPDF(table);
        });
    }

    // ─────────────────────────────────────────────────────────────────────
    // FUNCIONES PRIVADAS
    // ─────────────────────────────────────────────────────────────────────

    function _closeDetailModal() {
        if (detailModal) detailModal.classList.add('hidden');
        if (detailContent) detailContent.innerHTML = '';
        document.body.classList.remove('modal-open');
    }

    function _viewDetail(actionId) {
        if (!detailContent || !detailModal) return;

        detailContent.innerHTML = '<div style="display:flex;justify-content:center;align-items:center;padding:3rem;flex-direction:column;">' +
            '<div class="spinner-border text-primary" role="status" style="width:3rem;height:3rem;"></div>' +
            '<p class="mt-3 text-muted fw-bold">Cargando detalles...</p></div>';
        detailModal.classList.remove('hidden');
        document.body.classList.add('modal-open');

        fetch('/personnel_actions/' + actionId + '/detail/', {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(function (res) {
                if (!res.ok) throw new Error('No encontrado');
                return res.json();
            })
            .then(function (data) {
                detailContent.innerHTML = data.html;
                detailContent.querySelectorAll('.js-close-detail-modal').forEach(function (btn) {
                    btn.onclick = function () {
                        _closeDetailModal();
                    };
                });
            })
            .catch(function (err) {
                console.error('viewDetail error:', err);
                detailContent.innerHTML = '<div class="alert alert-danger m-4 text-center">' +
                    '<i class="fas fa-exclamation-circle fa-2x"></i>' +
                    '<p class="mt-2">No se pudo cargar la información.</p>' +
                    '<button class="btn btn-secondary mt-2" onclick="document.getElementById(\'actionDetailModal\').classList.add(\'hidden\')">Cerrar</button></div>';
            });
    }

    function _openEditModal(actionId) {
        var editContent = document.getElementById('modal-edit-content');
        var editModal = document.getElementById('actionEditModal');
        if (!editContent || !editModal) return;

        fetch('/personnel_actions/' + actionId + '/edit/', {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(function (res) {
                return res.text();
            })
            .then(function (html) {
                editContent.innerHTML = html;
                editModal.classList.remove('hidden');
                document.body.classList.add('modal-open');

                var closeEditModal = function () {
                    editModal.classList.add('hidden');
                    editContent.innerHTML = '';
                    document.body.classList.remove('modal-open');
                };
                window.closeModal = closeEditModal;

                editModal.addEventListener('click', function (ev) {
                    if (ev.target === editModal) closeEditModal();
                });

                // Select2
                try {
                    if (window.jQuery && jQuery.fn.select2) {
                        jQuery(editContent).find('.select2').each(function () {
                            jQuery(this).select2({width: '100%', dropdownParent: jQuery(editContent)});
                        });
                    }
                } catch (err) {
                    console.warn('Select2 init failed', err);
                }

                // Modal init
                try {
                    if (window.PersonnelActionModal && typeof PersonnelActionModal.init === 'function') {
                        PersonnelActionModal.init();
                    }
                } catch (err) {
                    console.warn('PersonnelActionModal init error', err);
                }

                // Submit AJAX
                var form = editContent.querySelector('form');
                if (form) {
                    form.addEventListener('submit', function (ev) {
                        ev.preventDefault();
                        fetch(form.action, {
                            method: 'POST',
                            body: new FormData(form),
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        })
                            .then(function (res) {
                                if (res.ok) {
                                    closeEditModal();
                                    window.fetchTableData();
                                    if (typeof Swal !== 'undefined') {
                                        Swal.fire({
                                            icon: 'success',
                                            title: 'Guardado',
                                            timer: 1200,
                                            showConfirmButton: false
                                        });
                                    }
                                } else {
                                    return res.text().then(function (txt) {
                                        editContent.innerHTML = txt;
                                    });
                                }
                            })
                            .catch(function (err) {
                                console.error('Edit submit error:', err);
                                if (typeof Swal !== 'undefined') Swal.fire('Error', 'Error inesperado', 'error');
                            });
                    });
                }

                var btnCancel = editContent.querySelector('.btn-cancel');
                if (btnCancel) btnCancel.addEventListener('click', function () {
                    if (window.closeModal) window.closeModal();
                });
            })
            .catch(function (err) {
                console.error('Edit modal error:', err);
                if (typeof Swal !== 'undefined') Swal.fire('Error', 'No se pudo abrir el formulario', 'error');
            });
    }

    function _confirmInactivate(actionId, number, csrf) {
        if (typeof Swal === 'undefined') {
            if (confirm('¿Está seguro de inactivar la acción ' + number + '? El número será reutilizado en la siguiente creación.')) {
                _doInactivate(actionId, csrf);
            }
            return;
        }

        Swal.fire({
            title: '¿Inactivar Acción?',
            text: 'La acción ' + number + ' será marcada como inactiva y su número podrá ser reutilizado si es la última creada.',
            icon: 'error',
            showCancelButton: true,
            confirmButtonColor: '#ef4444',
            cancelButtonColor: '#6b7280',
            confirmButtonText: 'Sí, inactivar',
            cancelButtonText: 'Cancelar'
        }).then(function (result) {
            if (result.isConfirmed) {
                _doInactivate(actionId, csrf);
            }
        });
    }

    function _doInactivate(actionId, csrf) {
        fetch('/personnel_actions/' + actionId + '/inactivate/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrf,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(res => {
                // Validamos si la respuesta es JSON antes de procesar
                if (!res.ok) throw new Error('Error en el servidor');
                return res.json();
            })
            .then(data => {
                if (data.success) {
                    Swal.fire('¡Anulada!', data.message, 'success');
                    window.fetchTableData(); // Recarga la tabla para reflejar los cambios
                } else {
                    Swal.fire('Atención', data.message || 'No se pudo inactivar', 'warning');
                }
            })
            .catch(err => {
                console.error('Error:', err);
                Swal.fire('Error', 'Hubo un problema al procesar la solicitud.', 'error');
            });
    }

    function _confirmRegister(actionId, csrf) {
        if (typeof Swal === 'undefined') {
            if (confirm('¿Está seguro de registrar esta acción?')) _doRegister(actionId, csrf);
            return;
        }
        Swal.fire({
            title: '¿Registrar Acción?',
            text: 'Una vez registrada, no podrá ser editada.',
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#3b82f6',
            cancelButtonColor: '#6b7280',
            confirmButtonText: 'Sí, registrar',
            cancelButtonText: 'Cancelar'
        }).then(function (result) {
            if (result.isConfirmed) _doRegister(actionId, csrf);
        });
    }

    function _doRegister(actionId, csrf) {
        fetch('/personnel_actions/' + actionId + '/register/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrf,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
            .then(function (res) {
                return res.json();
            })
            .then(function (data) {
                if (data.success) {
                    if (typeof Swal !== 'undefined') Swal.fire('¡Registrada!', data.message || 'Acción registrada correctamente', 'success');
                    window.fetchTableData();
                } else {
                    if (typeof Swal !== 'undefined') Swal.fire('Error', data.message || 'No se pudo registrar', 'error');
                }
            })
            .catch(function (err) {
                console.error('Register error:', err);
                if (typeof Swal !== 'undefined') Swal.fire('Error', 'Error de conexión', 'error');
            });
    }

    // ── Inicializar búsqueda rápida ───────────────────────────────────────
    initQuickSearch();

});