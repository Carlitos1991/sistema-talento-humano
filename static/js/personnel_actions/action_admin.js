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
    currentPage:      1,
    totalPages:       1,
    currentOrder:     null,
    currentDirection: 'asc',
};

/**
 * Recarga la tabla vía AJAX.
 * Expuesta globalmente para los onclick del partial HTML.
 */
window.fetchTableData = function (page) {
    const state       = window._paState;
    const container   = document.getElementById('table-content-wrapper');
    const urlList     = document.getElementById('url-list');
    const searchInput = document.getElementById('table-search');
    const filtersForm = document.getElementById('filtersForm');

    if (!container || !urlList) return;

    const pageNumber = (page != null) ? parseInt(page, 10) : state.currentPage;

    const params = new URLSearchParams();
    params.set('page', pageNumber);

    if (searchInput && searchInput.value.trim()) {
        params.set('q', searchInput.value.trim());
    }

    if (filtersForm) {
        new FormData(filtersForm).forEach(function (v, k) {
            if (v && v.toString().trim()) params.set(k, v);
        });
    }

    if (state.currentOrder) {
        params.set('order_by',  state.currentOrder);
        params.set('direction', state.currentDirection);
    }

    fetch(urlList.value + '?' + params.toString(), {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data.html) {
            container.innerHTML = data.html;
            _updateSortIcons();
        }
        state.currentPage = data.page_number || 1;
        state.totalPages  = data.num_pages   || 1;
    })
    .catch(function (err) {
        console.error('fetchTableData error:', err);
    });
};

/** Marca visualmente el encabezado de columna ordenado actualmente */
function _updateSortIcons() {
    var state = window._paState;
    document.querySelectorAll('a.sortable').forEach(function (el) {
        el.classList.remove('asc', 'desc');
        if (el.dataset.order === state.currentOrder) {
            el.classList.add(state.currentDirection);
        }
    });
}

// ─── Inicialización al cargar el DOM ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {

    var state = window._paState;

    // Leer paginación inicial inyectada por Django
    if (window.initialPagination) {
        state.currentPage = window.initialPagination.current_page || 1;
        state.totalPages  = window.initialPagination.total_pages  || 1;
    }

    var csrfToken   = (document.getElementById('csrf-token')  || {}).value || '';
    var tableContainer = document.getElementById('table-content-wrapper');
    var filtersForm    = document.getElementById('filtersForm');
    var detailModal    = document.getElementById('actionDetailModal');
    var detailContent  = document.getElementById('modal-detail-content');

    // ── Filtros: Buscar / Limpiar ─────────────────────────────────────────
    var btnSearch = document.getElementById('btn-filter-search');
    var btnClear  = document.getElementById('btn-filter-clear');

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
            state.currentPage = 1;
            window.fetchTableData(1);
        });
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
            state.currentOrder     = order;
            state.currentDirection = 'asc';
        }
        state.currentPage = 1;
        window.fetchTableData(1);
    });

    // ── Exportar ──────────────────────────────────────────────────────────
    var btnExportExcel = document.getElementById('btn-export-excel');
    var btnExportPdf   = document.getElementById('btn-export-pdf');
    if (btnExportExcel) {
        btnExportExcel.addEventListener('click', function (e) {
            e.preventDefault();
            var table = document.querySelector('.exportable-table');
            if (table && typeof exportTableCSVFallback === 'function') exportTableCSVFallback(table);
        });
    }
    if (btnExportPdf) {
        btnExportPdf.addEventListener('click', function (e) {
            e.preventDefault();
            var table = document.querySelector('.exportable-table');
            if (table && typeof exportTablePDFFallback === 'function') exportTablePDFFallback(table);
        });
    }

    // ─────────────────────────────────────────────────────────────────────
    // FUNCIONES PRIVADAS
    // ─────────────────────────────────────────────────────────────────────

    function _closeDetailModal() {
        if (detailModal)  detailModal.classList.add('hidden');
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
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(function (res) {
            if (!res.ok) throw new Error('No encontrado');
            return res.json();
        })
        .then(function (data) {
            detailContent.innerHTML = data.html;
            detailContent.querySelectorAll('.js-close-detail-modal').forEach(function (btn) {
                btn.onclick = function () { _closeDetailModal(); };
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
        var editModal   = document.getElementById('actionEditModal');
        if (!editContent || !editModal) return;

        fetch('/personnel_actions/' + actionId + '/edit/', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(function (res) { return res.text(); })
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
                        jQuery(this).select2({ width: '100%', dropdownParent: jQuery(editContent) });
                    });
                }
            } catch (err) { console.warn('Select2 init failed', err); }

            // Modal init
            try {
                if (window.PersonnelActionModal && typeof PersonnelActionModal.init === 'function') {
                    PersonnelActionModal.init();
                }
            } catch (err) { console.warn('PersonnelActionModal init error', err); }

            // Submit AJAX
            var form = editContent.querySelector('form');
            if (form) {
                form.addEventListener('submit', function (ev) {
                    ev.preventDefault();
                    fetch(form.action, {
                        method: 'POST',
                        body: new FormData(form),
                        headers: { 'X-Requested-With': 'XMLHttpRequest' }
                    })
                    .then(function (res) {
                        if (res.ok) {
                            closeEditModal();
                            window.fetchTableData();
                            if (typeof Swal !== 'undefined') {
                                Swal.fire({ icon: 'success', title: 'Guardado', timer: 1200, showConfirmButton: false });
                            }
                        } else {
                            return res.text().then(function (txt) { editContent.innerHTML = txt; });
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
            cancelButtonColor:  '#6b7280',
            confirmButtonText: 'Sí, registrar',
            cancelButtonText:  'Cancelar'
        }).then(function (result) {
            if (result.isConfirmed) _doRegister(actionId, csrf);
        });
    }

    function _doRegister(actionId, csrf) {
        fetch('/personnel_actions/' + actionId + '/register/', {
            method: 'POST',
            headers: {
                'X-CSRFToken':      csrf,
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(function (res) { return res.json(); })
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

});