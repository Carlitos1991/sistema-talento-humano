/* static/js/apps/person.js */

window.currentStatFilter = null;

// =========================================================================
// 1. FILTROS Y RECARGA DE TABLA
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

        // Reemplazo atómico idéntico a institution.js
        if (tableContainer && htmlToInject) {
            tableContainer.innerHTML = htmlToInject;
        }

        // Actualizar estadísticas si vienen en la respuesta
        if (statsToInject) {
            const statsRow = document.getElementById('statsRow');
            if (statsRow) statsRow.innerHTML = statsToInject;
        }

        // Reinicializar TableManager y utilidades sobre la tabla recién inyectada
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
            if (typeof addExportButtonsToTables === 'function') addExportButtonsToTables();
            if (typeof window.initTableHorizontalScroll === 'function') window.initTableHorizontalScroll();
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
// 2. UTILIDADES GLOBALES (Select2 y Scroll Horizontal)
// =========================================================================
window.initializeSelect2 = () => {
    if (!window.$ || !$.fn.select2) return;
    const $areaSelect = $('#filter_area');
    if (!$areaSelect.length) return;

    $areaSelect.siblings('.select2-container').remove();
    $areaSelect.removeClass('select2-hidden-accessible').removeAttr('data-select2-id tabindex aria-hidden');

    $areaSelect.select2({
        width: '100%', allowClear: true,
        placeholder: $areaSelect.data('placeholder') || 'Dependencia',
        language: {noResults: () => 'Sin resultados', searching: () => 'Buscando...'},
        ajax: {
            url: $areaSelect.data('ajax-url'),
            dataType: 'json', delay: 250,
            data: (params) => ({term: params.term}),
            processResults: (data) => {
                if (Array.isArray(data.units)) return {
                    results: data.units.map(u => ({
                        id: String(u.id),
                        text: u.name
                    }))
                };
                return {results: []};
            }
        }
    });
};

window.initTableHorizontalScroll = () => {
    const tc = document.querySelector('.table-container');
    if (!tc) return;
    tc.classList.add('table-container-has-scroll-helper');
    let helperGroup = tc.querySelector('.table-scroll-helper-group');

    if (!helperGroup) {
        helperGroup = document.createElement('div');
        helperGroup.className = 'table-scroll-helper-group';
        helperGroup.innerHTML = `
            <button class="table-scroll-nav-button table-scroll-nav-start"><i class="fas fa-angles-left"></i></button>
            <button class="table-scroll-nav-button table-scroll-nav-end"><i class="fas fa-angles-right"></i></button>`;
        tc.appendChild(helperGroup);
    }

    const updateScrollIndicator = () => {
        const hasScroll = tc.scrollWidth > tc.clientWidth;
        const atStart = tc.scrollLeft <= 4;
        const atEnd = tc.scrollLeft + tc.clientWidth >= tc.scrollWidth - 4;

        tc.classList.toggle('table-scroll-helper-force-visible', hasScroll);
        tc.classList.toggle('table-scroll-helper-at-end', hasScroll && atEnd && !atStart);

        const startBtn = tc.querySelector('.table-scroll-nav-start');
        const endBtn = tc.querySelector('.table-scroll-nav-end');

        if (startBtn) {
            startBtn.style.display = hasScroll && atEnd ? 'inline-flex' : 'none';
            startBtn.onclick = () => tc.scrollTo({left: 0, behavior: 'smooth'});
        }
        if (endBtn) {
            endBtn.style.display = hasScroll && !atEnd ? 'inline-flex' : 'none';
            endBtn.onclick = () => tc.scrollTo({left: tc.scrollWidth, behavior: 'smooth'});
        }
    };
    updateScrollIndicator();
    window.addEventListener('resize', updateScrollIndicator);
    tc.addEventListener('scroll', updateScrollIndicator);
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
            const $select = $('<select>').addClass('form-control select2-relocate w-full border p-2 rounded').css('width', '100%').append('<option value="">-- Seleccione --</option>');
            data.units.forEach(u => $select.append(`<option value="${u.id}" data-has-children="${u.has_children}">${u.name}</option>`));

            const $wrapper = $('<div class="form-group mb-3"></div>').append('<label class="text-xs font-bold text-gray-600 mb-1 block">Seleccione Unidad:</label>').append($select);
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
// 4. INICIALIZACIÓN DE EVENTOS DEL DOM
// =========================================================================
document.addEventListener('DOMContentLoaded', () => {
    window.initializeSelect2();
    if (typeof window.initTableHorizontalScroll === 'function') window.initTableHorizontalScroll();

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
});