/* static/js/documents/documents.js
   Gestión Documental integrada al 100% con main.js
*/

(function () {
    'use strict';

    const docState = {
        selectedTypeId: '',
        dateFrom: null,
        dateTo: null
    };

    document.addEventListener('DOMContentLoaded', () => {
        const fromInput = document.getElementById('stats-date-from');
        const toInput = document.getElementById('stats-date-to');
        if (fromInput) docState.dateFrom = fromInput.value || null;
        if (toInput) docState.dateTo = toInput.value || null;

        [fromInput, toInput].forEach(input => {
            if (!input) return;
            input.addEventListener('change', () => {
                docState.dateFrom = fromInput ? fromInput.value : null;
                docState.dateTo = toInput ? toInput.value : null;
                applyFilters(1);
            });
        });

        setAddButtonEnabled(false);
    });

    function applyFilters(page = 1) {
        const params = {
            page: page,
            documents: docState.selectedTypeId || ''
        };
        if (docState.dateFrom) params.date_from = docState.dateFrom;
        if (docState.dateTo) params.date_to = docState.dateTo;

        // Recarga de tabla universal de main.js
        window.refreshCurrentTable(params, updateStats);
    }

    function updateStats() {
        const params = new URLSearchParams();
        if (docState.dateFrom) params.append('date_from', docState.dateFrom);
        if (docState.dateTo) params.append('date_to', docState.dateTo);

        fetch(`${window.location.pathname}?${params.toString()}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(res => res.json())
            .then(data => {
                if (!data.stats) return;
                const totalEl = document.getElementById('stat-display-total');
                if (totalEl) totalEl.textContent = data.stats.total || 0;

                if (Array.isArray(data.stats.regimes)) {
                    data.stats.regimes.forEach(r => {
                        const card = document.querySelector(`.stat-card[data-code="${r.code}"]`);
                        if (card) {
                            const countEl = card.querySelector('.stat-regime-count');
                            if (countEl) countEl.textContent = r.count || 0;
                        }
                    });
                }
            })
            .catch(err => console.error('Error al actualizar estadísticas:', err));
    }

    function setAddButtonEnabled(enabled) {
        const btn = document.getElementById('btn-add-document');
        if (!btn) return;
        btn.disabled = !enabled;
        btn.style.opacity = enabled ? '1' : '0.6';
        btn.style.pointerEvents = enabled ? 'auto' : 'none';
        btn.style.cursor = enabled ? 'pointer' : 'not-allowed';
    }

    // Filtrar por tarjeta superior
    window.filterByRegime = function (regimeCode) {
        const codeStr = String(regimeCode || '');
        const cards = document.querySelectorAll('#document-stats-row .stat-card');

        if (docState.selectedTypeId === codeStr) {
            docState.selectedTypeId = '';
            cards.forEach(c => c.classList.remove('opacity-low'));
            setAddButtonEnabled(false);
        } else {
            docState.selectedTypeId = codeStr;
            cards.forEach(c => {
                if (!codeStr) {
                    c.classList.remove('opacity-low');
                } else {
                    c.classList.toggle('opacity-low', c.dataset.code !== codeStr);
                }
            });
            setAddButtonEnabled(codeStr !== '');
        }

        applyFilters(1);
    };

    window.changeDocumentPage = function (page) {
        applyFilters(page);
    };

    // Apertura del modal crear usando openAjaxModal de main.js
    window.openCreateDocumentModal = function () {
        if (!docState.selectedTypeId) {
            Swal.fire({
                icon: 'info',
                title: 'Atención',
                text: 'Seleccione primero un tipo de documento en las tarjetas superiores.'
            });
            return;
        }
        window.openAjaxModal(`/documents/create/?category_id=${docState.selectedTypeId}`);
    };

    // Subida rápida de PDF desde la tabla
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
                    applyFilters();
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

    // Toggle reutilizando toggleStatusAjax de main.js
    window.toggleTypeStatus = function (url, typeName, currentStatus) {
        window.toggleStatusAjax(url, typeName, currentStatus, () => {
            applyFilters();
        });
    };

})();