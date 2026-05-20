(function () {
    'use strict';

    const tableContainer = document.getElementById('table-content-wrapper');
    const filtersForm = document.getElementById('filtersForm');
    const searchInput = document.getElementById('table-search-permits');
    const areaSelect = document.getElementById('filter_area');
    const permitTypeSelect = document.getElementById('filter_permit_type');
    const permitSubtypeSelect = document.getElementById('filter_permit_subtype');
    const statusSelect = document.getElementById('filter_status');
    const dateFromInput = document.getElementById('filter_date_from');
    const dateToInput = document.getElementById('filter_date_to');
    const modalOverlay = document.getElementById('modal-overlay');
    const modalContentContainer = document.getElementById('modal-content-container');
    const modalResponseOverlay = document.getElementById('modal-response-overlay');
    const modalResponseContainer = document.getElementById('modal-response-container');

    const urlList = '/permitrequest/admin/';
    let currentPage = 1;
    let currentSortField = 'start_date';
    let currentSortDir = 'desc';
    let searchTimeout = null;

    function getSearchValue() {
        return searchInput && searchInput.value ? searchInput.value.trim() : '';
    }

    // No subtypes in this layout; keep function stub for compatibility
    function syncSubtypeOptions() { return; }

    function collectFilters() {
        return {
            q: getSearchValue(),
            area: areaSelect ? areaSelect.value : '',
            permit_type: permitTypeSelect ? permitTypeSelect.value : '',
            status: statusSelect ? statusSelect.value : '',
            date_from: dateFromInput ? dateFromInput.value : '',
            date_to: dateToInput ? dateToInput.value : '',
            sort_field: currentSortField,
            sort_dir: currentSortDir,
        };
    }

    function updateSortIndicators() {
        const table = document.getElementById('permitAdminTable');
        if (!table) {
            return;
        }

        table.querySelectorAll('thead th[data-field]').forEach((th) => {
            const field = th.dataset.field;
            const icon = th.querySelector('.sort-icon');
            th.classList.remove('sorted-asc', 'sorted-desc');
            if (icon) {
                icon.textContent = '⇅';
            }
            if (field === currentSortField) {
                th.classList.add(currentSortDir === 'asc' ? 'sorted-asc' : 'sorted-desc');
                if (icon) {
                    icon.textContent = currentSortDir === 'asc' ? '↑' : '↓';
                }
            }
        });
    }

    function updatePagination(paginationData) {
        const paginationInfo = document.querySelector('.pagination-info');
        const paginationControls = document.querySelector('.pagination-controls');
        const pageInput = document.querySelector('.page-input');
        if (!paginationData) {
            return;
        }

        if (paginationInfo) {
            paginationInfo.textContent = `Mostrando ${paginationData.start_index || 0}-${paginationData.end_index || 0} de ${paginationData.total_count || 0}`;
        }

        if (pageInput) {
            pageInput.value = paginationData.page || 1;
            pageInput.max = paginationData.total_pages || 1;
        }

        if (paginationControls) {
            paginationControls.style.visibility = (paginationData.total_pages || 1) <= 1 ? 'hidden' : 'visible';
        }
    }

    function attachRowActionListeners() {
        document.querySelectorAll('.js-view-detail').forEach((btn) => {
            btn.onclick = function () {
                openDetailModal(this.dataset.permitId);
            };
        });

        document.querySelectorAll('.js-approve-permit').forEach((btn) => {
            btn.onclick = function () {
                openResponseModal(this.dataset.permitId, 'approve');
            };
        });

        document.querySelectorAll('.js-reject-permit').forEach((btn) => {
            btn.onclick = function () {
                openResponseModal(this.dataset.permitId, 'reject');
            };
        });

        document.querySelectorAll('.js-print-permit').forEach((btn) => {
            btn.onclick = function () {
                printPermitReport(this.dataset.permitId);
            };
        });
    }

    function refreshTableButtons() {
        if (typeof window.addExportButtonsToTables === 'function') {
            window.addExportButtonsToTables();
        }
    }

    function fetchTableData() {
        if (!tableContainer) {
            return;
        }

        const params = new URLSearchParams(collectFilters());
        params.set('page', currentPage);

        fetch(`${urlList}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then((response) => response.json())
            .then((data) => {
                if (!data.success) {
                    throw new Error(data.message || 'No se pudo cargar la tabla');
                }

                tableContainer.innerHTML = data.html;
                updatePagination(data.pagination);
                updateSortIndicators();
                attachRowActionListeners();
                refreshTableButtons();
            })
            .catch((error) => {
                console.error('Error al cargar permisos:', error);
                if (window.Swal) {
                    Swal.fire('Error', 'No se pudo cargar el listado de permisos', 'error');
                }
            });
    }

    function handleFilterChange() {
        currentPage = 1;
        fetchTableData();
    }

    window.changePage = function (page) {
        const targetPage = parseInt(page, 10) || 1;
        currentPage = targetPage < 1 ? 1 : targetPage;
        fetchTableData();
    };

    window.sortPermitAdminTable = function (thElement) {
        if (!thElement || !thElement.dataset || !thElement.dataset.field) {
            return;
        }

        const field = thElement.dataset.field;
        if (currentSortField === field) {
            currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
        } else {
            currentSortField = field;
            currentSortDir = 'asc';
        }

        currentPage = 1;
        updateSortIndicators();
        fetchTableData();
    };

    window.fetchPeople = fetchTableData;

    window._personExport = {
        listUrl: urlList,
        getFilters: collectFilters
    };

    // Enter on main search triggers fetch
    if (searchInput) {
        searchInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                currentPage = 1;
                fetchTableData();
            }
        });
    }

    const btnSearch = document.getElementById('btn-search-permits');
    const btnClear = document.getElementById('btn-clear-permits');

    if (btnSearch) {
        btnSearch.addEventListener('click', function () {
            currentPage = 1;
            fetchTableData();
        });
    }

    if (btnClear) {
        btnClear.addEventListener('click', function () {
            if (filtersForm) {
                filtersForm.reset();
            }
            currentPage = 1;
            fetchTableData();
        });
    }

    if (permitTypeSelect) {
        permitTypeSelect.addEventListener('change', handleFilterChange);
    }

    if (areaSelect) {
        areaSelect.addEventListener('change', handleFilterChange);
    }

    if (statusSelect) {
        statusSelect.addEventListener('change', handleFilterChange);
    }

    if (dateFromInput) {
        dateFromInput.addEventListener('change', handleFilterChange);
    }

    if (dateToInput) {
        dateToInput.addEventListener('change', handleFilterChange);
    }

    if (filtersForm) {
        filtersForm.addEventListener('submit', function (event) {
            event.preventDefault();
            handleFilterChange();
        });
    }

    // Inicializar Select2 para selects con data-ajax-url (si jQuery + Select2 están presentes)
    try {
        if (window.$ && $.fn.select2) {
            document.querySelectorAll('select.select2').forEach(function (sel) {
                try {
                    if ($(sel).hasClass('select2-hidden-accessible')) {
                        $(sel).select2('destroy');
                    }
                } catch (e) {}

                const ajaxUrl = sel.dataset.ajaxUrl;
                const placeholder = sel.dataset.placeholder || '';
                const minLen = parseInt(sel.dataset.minimumInputLength || '1', 10) || 1;

                if (ajaxUrl) {
                    $(sel).select2({
                        placeholder: placeholder,
                        allowClear: true,
                        minimumInputLength: minLen,
                        ajax: {
                            url: ajaxUrl,
                            dataType: 'json',
                            delay: 250,
                            data: function (params) {
                                return {term: params.term};
                            },
                            processResults: function (data) {
                                return {results: data.results || []};
                            },
                            cache: true
                        },
                        width: '100%'
                    });
                } else {
                    $(sel).select2({placeholder: placeholder, allowClear: true, width: '100%'});
                }
            });
        }
    } catch (e) {
        console.warn('Select2 init failed for permit_admin filters', e);
    }

    function openDetailModal(permitId) {
        const url = `/permitrequest/admin/${permitId}/detail/`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then((response) => response.text())
            .then((html) => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.style.overflow = 'hidden';

                document.querySelectorAll('.js-close-modal').forEach((btn) => {
                    btn.addEventListener('click', closeDetailModal);
                });
            })
            .catch((error) => {
                console.error('Error al abrir modal:', error);
                if (window.Swal) {
                    Swal.fire('Error', 'No se pudo cargar el detalle', 'error');
                }
            });
    }

    function closeDetailModal() {
        modalOverlay.classList.add('hidden');
        modalContentContainer.innerHTML = '';
        document.body.style.overflow = '';
    }

    function openResponseModal(permitId, action) {
        const url = `/permitrequest/admin/${permitId}/${action}/`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then((response) => response.text())
            .then((html) => {
                modalResponseContainer.innerHTML = html;
                modalResponseOverlay.classList.remove('hidden');
                document.body.style.overflow = 'hidden';

                document.querySelectorAll('.js-close-response-modal').forEach((btn) => {
                    btn.addEventListener('click', closeResponseModal);
                });

                const form = document.getElementById('responsePermitForm');
                if (form) {
                    form.addEventListener('submit', (event) => handleResponseSubmit(event, permitId, action));
                }
            })
            .catch((error) => {
                console.error('Error al abrir modal:', error);
                if (window.Swal) {
                    Swal.fire('Error', 'No se pudo cargar el formulario', 'error');
                }
            });
    }

    function closeResponseModal() {
        modalResponseOverlay.classList.add('hidden');
        modalResponseContainer.innerHTML = '';
        document.body.style.overflow = '';
    }

    function printPermitReport(permitId) {
        const url = `/permitrequest/admin/${permitId}/report/`;
        window.open(url, '_blank', 'width=800,height=600');
    }

    function handleResponseSubmit(event, permitId, action) {
        event.preventDefault();
        const formData = new FormData(event.target);
        const url = `/permitrequest/admin/${permitId}/${action}/`;

        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then((response) => response.json())
            .then((data) => {
                if (data.success) {
                    closeResponseModal();
                    if (window.Swal) {
                        Swal.fire({
                            icon: 'success',
                            title: 'Éxito',
                            text: data.message,
                            timer: 2000,
                            showConfirmButton: false
                        });
                    }
                    fetchTableData();
                } else {
                    if (window.Swal) {
                        Swal.fire('Error', data.message || 'Ocurrió un error', 'error');
                    }
                }
            })
            .catch((error) => {
                console.error(error);
                if (window.Swal) {
                    Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
                }
            });
    }

    syncSubtypeOptions();
    updateSortIndicators();
    attachRowActionListeners();
    refreshTableButtons();
})();
