/* static/js/documents/documents.js */
(function () {
    'use strict';

    window.applyDocumentFilters = async function (page = 1) {
        const form = document.getElementById('documentFiltersForm');
        if (!form) return;

        const params = new URLSearchParams();
        params.set('page', page);

        const q = form.querySelector('input[name="q"]')?.value.trim();
        const dateFrom = form.querySelector('input[name="date_from"]')?.value;
        const dateTo = form.querySelector('input[name="date_to"]')?.value;
        const documentType = form.querySelector('input[name="documents"]')?.value;

        if (q) params.set('q', q);
        if (dateFrom) params.set('date_from', dateFrom);
        if (dateTo) params.set('date_to', dateTo);
        if (documentType) params.set('documents', documentType);

        if (window._currentTableSort) {
            const ths = document.querySelectorAll('.managed-table thead th');
            const th = ths[window._currentTableSort.col];
            if (th && th.dataset.field) {
                params.set('sort_field', th.dataset.field);
                params.set('sort_dir', window._currentTableSort.asc ? 'asc' : 'desc');
            }
        }

        const listUrl = document.querySelector('.managed-table')?.dataset.listUrl || window.location.pathname;
        const tableContainer = document.getElementById('tableContainer');

        if (tableContainer) {
            tableContainer.style.opacity = '0.4';
            tableContainer.style.pointerEvents = 'none';
        }

        try {
            const res = await fetch(`${listUrl}?${params.toString()}`, {
                headers: {'X-Requested-With': 'XMLHttpRequest'}
            });

            const contentType = res.headers.get("content-type");
            let htmlToInject = "";
            let statsToInject = "";

            if (contentType && contentType.includes("application/json")) {
                const data = await res.json();
                htmlToInject = data.html || '';
                statsToInject = data.stats_html || '';
            } else {
                htmlToInject = await res.text();
            }

            if (tableContainer && htmlToInject) {
                tableContainer.innerHTML = htmlToInject;
            }

            if (statsToInject) {
                const statsRow = document.getElementById('documentStatsRow');
                if (statsRow) statsRow.innerHTML = statsToInject;
            }

            setTimeout(() => {
                const newTable = document.querySelector('.managed-table');
                if (newTable) {
                    new TableManager(newTable);
                    if (window._currentTableSort) {
                        const sortedTh = newTable.querySelectorAll('thead th')[window._currentTableSort.col];
                        if (sortedTh) {
                            sortedTh.classList.add(window._currentTableSort.asc ? 'sorted-asc' : 'sorted-desc');
                            const arrow = sortedTh.querySelector('.sort-arrow');
                            if (arrow) arrow.innerText = window._currentTableSort.asc ? '↑' : '↓';
                        }
                    }
                }
            }, 50);

        } catch (e) {
            console.error('Error AJAX:', e);
        } finally {
            if (tableContainer) {
                tableContainer.style.opacity = '1';
                tableContainer.style.pointerEvents = 'auto';
            }
        }
    };

    window.filterByRegime = function (typeId) {
        const hiddenInput = document.getElementById('filter_document_type');
        const codeStr = String(typeId || '');

        if (hiddenInput.value === codeStr) {
            hiddenInput.value = '';
        } else {
            hiddenInput.value = codeStr;
        }

        setAddButtonEnabled(hiddenInput.value !== '');
        window.applyDocumentFilters(1);
    };

    function setAddButtonEnabled(enabled) {
        const btn = document.getElementById('btn-add-document');
        if (!btn) return;
        btn.disabled = !enabled;
        btn.style.opacity = enabled ? '1' : '0.6';
        btn.style.pointerEvents = enabled ? 'auto' : 'none';
        btn.style.cursor = enabled ? 'pointer' : 'not-allowed';
    }

    document.addEventListener('DOMContentLoaded', () => {
        setAddButtonEnabled(false);

        // Envío de búsqueda y filtros
        document.getElementById('documentFiltersForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            window.applyDocumentFilters(1);
        });

        // Búsqueda en tiempo real con debounce
        let searchTimer = null;
        document.getElementById('searchInput')?.addEventListener('input', () => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                window.applyDocumentFilters(1);
            }, 350);
        });

        // Limpiar formulario
        document.getElementById('documentFiltersClear')?.addEventListener('click', () => {
            const form = document.getElementById('documentFiltersForm');
            if (form) form.reset();
            const hiddenType = document.getElementById('filter_document_type');
            if (hiddenType) hiddenType.value = '';
            setAddButtonEnabled(false);
            window.applyDocumentFilters(1);
        });
    });

    // Paginador delegado: escucha los clics en los botones .page-btn de la tabla
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('#tableContainer .page-btn');
        if (!btn) return;

        if (btn.disabled || btn.classList.contains('disabled')) return;
        e.preventDefault();
        e.stopPropagation();

        const page = btn.dataset.page;
        if (page) {
            window.applyDocumentFilters(parseInt(page) || 1);
        }
    });

    window.openCreateDocumentModal = function () {
        const currentType = document.getElementById('filter_document_type')?.value;
        if (!currentType) {
            Swal.fire({
                icon: 'info',
                title: 'Atención',
                text: 'Seleccione primero un tipo de documento en las tarjetas superiores.'
            });
            return;
        }
        window.openAjaxModal(`/documents/create/?category_id=${currentType}`);
    };

    window.uploadDocumentFile = function (id) {
        if (!id) return;
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'application/pdf';
        fileInput.style.display = 'none';
        document.body.appendChild(fileInput);

        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) {
                document.body.removeChild(fileInput);
                return;
            }

            const fd = new FormData();
            fd.append('file', file);

            try {
                const res = await fetch(`/documents/upload-file/${id}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: fd
                });
                const data = await res.json();
                if (data.success) {
                    window.showToast(data.message || 'Archivo subido con éxito.', 'success');
                    window.applyDocumentFilters();
                } else {
                    Swal.fire({icon: 'error', title: 'Error', text: data.message || 'Error al subir archivo.'});
                }
            } catch (err) {
                console.error(err);
                Swal.fire({icon: 'error', title: 'Error', text: 'Error de comunicación con el servidor.'});
            } finally {
                document.body.removeChild(fileInput);
            }
        });

        fileInput.click();
    };
})();