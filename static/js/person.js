/* static/js/apps/person.js */

window.currentStatFilter = null;

// =========================================================================
// 1. FILTROS Y RECARGA AJAX DE LA TABLA DE PERSONAS
// =========================================================================
window.applyPersonFilters = async function (page = 1) {
    const form = document.getElementById('personFiltersForm');
    if (!form) return;

    const params = new URLSearchParams();
    params.set('page', page);

    const q = form.querySelector('input[name="q"]')?.value.trim();
    const area = form.querySelector('select[name="area"]')?.value;
    const isActive = form.querySelector('select[name="is_active"]')?.value;

    if (q) params.set('q', q);
    if (area) params.set('area', area);
    if (isActive) params.set('is_active', isActive);
    if (window.currentStatFilter) params.set('status', window.currentStatFilter);

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
            const statsRow = document.getElementById('statsRow');
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

window.quickFilterStatus = function (statusValue) {
    const statusSelect = document.querySelector('select[name="is_active"]');
    if (statusSelect) {
        statusSelect.value = statusValue;
        if ($(statusSelect).hasClass('select2-hidden-accessible')) $(statusSelect).trigger('change.select2');
    }
    window.currentStatFilter = statusValue;
    window.applyPersonFilters(1);
};

// =========================================================================
// 2. UTILIDADES DE FORMULARIO (Select2 de dependencias en filtro)
// =========================================================================
window.initializeSelect2 = () => {
    if (!window.$ || !$.fn.select2) return;
    const $areaSelect = $('#filter_area');
    if (!$areaSelect.length) return;

    $areaSelect.siblings('.select2-container').remove();
    $areaSelect.removeClass('select2-hidden-accessible').removeAttr('data-select2-id tabindex aria-hidden');

    $areaSelect.select2({
        width: '100%',
        allowClear: true,
        placeholder: $areaSelect.data('placeholder') || 'Dependencia',
        language: {
            noResults: () => 'Sin resultados',
            searching: () => 'Buscando...'
        },
        ajax: {
            url: $areaSelect.data('ajax-url'),
            dataType: 'json',
            delay: 250,
            data: (params) => ({term: params.term}),
            processResults: (data) => {
                if (Array.isArray(data.units)) {
                    return {
                        results: data.units.map(u => ({
                            id: String(u.id),
                            text: u.name
                        }))
                    };
                }
                return {results: []};
            }
        }
    });
};

// =========================================================================
// 3. REUBICACIÓN DE EMPLEADOS
// =========================================================================
window.openRelocateEmployeeModal = function (personId, personFullName, personArea) {
    window.selectedRelocatePersonId = personId;
    window.selectedRelocatePersonName = personFullName;
    window.selectedRelocatePersonArea = personArea;
    $('#relocate-combos-wrapper').empty();
    openModal('modal-relocate-employee');
    loadUnitLevel(null);
};

function loadUnitLevel(parentId) {
    $.ajax({
        url: '/institution/api/unit-children/',
        data: parentId ? {parent_id: parentId} : {},
        success: function (data) {
            if (!data.units || data.units.length === 0) return;
            const $select = $('<select>')
                .addClass('form-control select2-relocate w-full border p-2 rounded')
                .css('width', '100%')
                .append('<option value="">-- Seleccione --</option>');

            data.units.forEach(u => $select.append(`<option value="${u.id}" data-has-children="${u.has_children}">${u.name}</option>`));

            const $wrapper = $('<div class="form-group mb-3"></div>')
                .append('<label class="text-xs font-bold text-gray-600 mb-1 block">Seleccione Unidad:</label>')
                .append($select);

            $('#relocate-combos-wrapper').append($wrapper);

            if ($.fn.select2) $select.select2({dropdownParent: $('#modal-relocate-employee'), width: '100%'});

            $select.on('change', function () {
                const val = $(this).val();
                $(this).closest('.form-group').nextAll().remove();
                if (val && $(this).find(':selected').data('has-children')) loadUnitLevel(val);
            });
        }
    });
}

// =========================================================================
// 4. SUBIDA DE HOJA DE VIDA (PDF)
// =========================================================================
window.uploadCvPdf = function (input, personId) {
    if (!input.files || !input.files[0]) return;

    const file = input.files[0];

    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        Swal.fire({
            icon: 'warning',
            title: 'Formato no válido',
            text: 'Por favor, seleccione un documento en formato PDF.'
        });
        input.value = '';
        return;
    }

    if (file.size > 5 * 1024 * 1024) {
        Swal.fire({
            icon: 'warning',
            title: 'Archivo muy pesado',
            text: 'El archivo no debe superar los 5 MB.'
        });
        input.value = '';
        return;
    }

    const formData = new FormData();
    formData.append('pdf_file', file);

    showToast('Subiendo hoja de vida...', 'info');

    fetch(`/employee/api/upload-cv/${personId}/`, {
        method: 'POST',
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''
        },
        body: formData
    })
        .then(async res => {
            const data = await res.json();
            if (res.ok && data.success) {
                showToast(data.message || 'Hoja de vida subida con éxito.', 'success');
                setTimeout(() => location.reload(), 800);
            } else {
                Swal.fire({
                    icon: 'error',
                    title: 'Error al subir',
                    text: data.message || 'No se pudo guardar la hoja de vida.'
                });
            }
        })
        .catch(err => {
            console.error('Error subiendo PDF de CV:', err);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Ocurrió un problema de comunicación con el servidor.'
            });
        })
        .finally(() => {
            input.value = '';
        });
};

// =========================================================================
// 5. INICIALIZACIÓN UNIFICADA DE EVENTOS DEL DOM
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    window.initializeSelect2();

    // Filtros de búsqueda
    document.getElementById('personFiltersForm')?.addEventListener('submit', (e) => {
        e.preventDefault();
        window.applyPersonFilters(1);
    });

    document.getElementById('personFiltersClear')?.addEventListener('click', () => {
        const form = document.getElementById('personFiltersForm');
        if (form) form.reset();
        window.currentStatFilter = null;
        const $areaSelect = $('#filter_area');
        if ($areaSelect.length) $areaSelect.val(null).trigger('change');
        window.applyPersonFilters(1);
    });

    // Guardar reubicación de empleado
    $(document).on('submit', '#form-relocate-employee', function (e) {
        e.preventDefault();
        let finalUnitId = null;
        $('#relocate-combos-wrapper select').each(function () {
            if ($(this).val()) finalUnitId = $(this).val();
        });

        if (!finalUnitId) {
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'warning',
                title: 'Seleccione unidad',
                showConfirmButton: false,
                timer: 2500
            });
            return;
        }

        const btn = $(this).find('button[type="submit"]');
        const originalText = btn.html();
        btn.prop('disabled', true).html('Guardando...');

        $.ajax({
            url: '/person/relocate/',
            method: 'POST',
            headers: {'X-CSRFToken': typeof getCSRF === 'function' ? getCSRF() : ''},
            data: {person_id: window.selectedRelocatePersonId, unit_id: finalUnitId},
            success: function (resp) {
                if (resp.success) {
                    Swal.fire({
                        toast: true,
                        position: 'top-end',
                        icon: 'success',
                        title: 'Reubicación exitosa',
                        showConfirmButton: false,
                        timer: 3500
                    });
                    closeModal('modal-relocate-employee');
                    setTimeout(() => location.reload(), 1800);
                } else {
                    Swal.fire({
                        toast: true,
                        position: 'top-end',
                        icon: 'error',
                        title: resp.message,
                        showConfirmButton: false,
                        timer: 2500
                    });
                }
            },
            complete: () => btn.prop('disabled', false).html(originalText)
        });
    });

    // Previsualización de foto (usa la función universal de main.js)
    document.getElementById('id_photo')?.addEventListener('change', function () {
        if (typeof handleModalPhotoPreview === 'function') {
            handleModalPhotoPreview(this);
        }
    });

    // Combos dependientes DPA (País -> Provincia -> Cantón -> Parroquia)
    $('#id_country').on('change', function () {
        if ($(this).val()) {
            handleLocationCascade(this, 'id_province');
        }
        $('#id_canton').empty().append('<option value="">-- Seleccione --</option>').trigger('change');
        $('#id_parish').empty().append('<option value="">-- Seleccione --</option>').trigger('change');
    });

    $('#id_province').on('change', function () {
        if ($(this).val()) {
            handleLocationCascade(this, 'id_canton');
        }
        $('#id_parish').empty().append('<option value="">-- Seleccione --</option>').trigger('change');
    });

    $('#id_canton').on('change', function () {
        if ($(this).val()) {
            handleLocationCascade(this, 'id_parish');
        }
    });
});