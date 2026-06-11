
// ── Abre el modal y carga el formulario desde la URL dada ─────────────────
function openRubricModal(url) {
    const modalEl = document.getElementById('rubricModal');
    const modalBody = document.getElementById('rubricModalBody');

    if (!modalEl || !modalBody) {
        console.error('[RubricModal] No se encontró #rubricModal o #rubricModalBody en el DOM.');
        return;
    }

    // Mostrar spinner mientras carga
    modalBody.innerHTML = `
        <div class="text-center py-5">
            <div class="spinner-border text-primary" role="status"></div>
            <p class="mt-2 text-muted">Cargando rubro...</p>
        </div>`;

    // Mostrar modal (Bootstrap 5)
    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    // Cargar HTML del formulario vía AJAX
    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(res => {
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            return res.text();
        })
        .then(html => {
            modalBody.innerHTML = html;
            _initModalSelects(modalBody);  // ← inicializar DESPUÉS de tener el HTML
        })
        .catch(err => {
            modalBody.innerHTML = `
                <div class="alert alert-danger m-3">
                    Error al cargar el formulario: ${err.message}
                </div>`;
        });
}

// ── Inicializa todos los selects del modal ────────────────────────────────
function _initModalSelects(container) {
    // Destruir instancias previas de Select2 dentro del container
    // para evitar duplicados si el modal se reabre
    $(container).find('select').each(function () {
        if ($(this).hasClass('select2-hidden-accessible')) {
            $(this).select2('destroy');
        }
    });

    // Re-inicializar Select2 en todos los selects del modal
    // dropdownParent es clave: hace que el dropdown aparezca DENTRO
    // del modal y no quede oculto detrás del overlay.
    $(container).find('select').select2({
        width: '100%',
        dropdownParent: $('#rubricModal'),
        allowClear: true,
        placeholder: '---------',
    });

    // Pre-seleccionar los valores guardados.
    // Django debe renderizar cada <select> con el atributo
    //   data-selected-id="{{ form.income_account.value }}"
    // o simplemente con el <option selected> correcto (lo hace por defecto
    // si se usa ModelChoiceField). En ese caso Select2 lo respeta solo.
    // Este bloque es el seguro extra para cuando Select2 no lo detecta:
    $(container).find('select[data-selected-id]').each(function () {
        const selectedId = $(this).data('selected-id');
        if (selectedId) {
            $(this).val(selectedId).trigger('change');
        }
    });

    // Inicializar cualquier otro JS del formulario (checkboxes, toggles, etc.)
    _initModalToggles(container);
}

// ── Manejo de toggles internos del formulario ─────────────────────────────
function _initModalToggles(container) {
    // Toggle: mostrar/ocultar secciones de cuentas por contexto
    const contextSelect = container.querySelector('select[name="spending_context"]');
    if (contextSelect) {
        _applyContextVisibility(contextSelect.value, container);
        contextSelect.addEventListener('change', function () {
            _applyContextVisibility(this.value, container);
        });
    }

    // Toggle: checkbox "¿Afecta al Presupuesto?"
    const mappingCheck = container.querySelector('input[name="has_mapping"]');
    const mappingSection = container.querySelector('#mappingSection');
    if (mappingCheck && mappingSection) {
        mappingSection.style.display = mappingCheck.checked ? 'block' : 'none';
        mappingCheck.addEventListener('change', function () {
            mappingSection.style.display = this.checked ? 'block' : 'none';
        });
    }
}

// ── Muestra solo la sección de cuentas del contexto seleccionado ──────────
function _applyContextVisibility(contextValue, container) {
    const sections = {
        'base': container.querySelector('#cuentasBase'),
        'inv': container.querySelector('#cuentasInversion'),
        'prod': container.querySelector('#cuentasProduccion'),
    };

    // Por defecto: siempre visible la sección base (5.1/TODOS)
    if (sections.base) sections.base.style.display = 'block';
    if (sections.inv) sections.inv.style.display = contextValue === '7.1' ? 'block' : 'none';
    if (sections.prod) sections.prod.style.display = contextValue === '6.1' ? 'block' : 'none';
}

// ── Envío del formulario vía AJAX (sin recargar la página) ────────────────
function submitRubricForm(event) {
    event.preventDefault();
    const form = event.target;
    const url = form.action;
    const formData = new FormData(form);

    fetch(url, {
        method: 'POST',
        body: formData,
        headers: {'X-Requested-With': 'XMLHttpRequest'},
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                // Cerrar modal y recargar tabla sin recargar la página completa
                bootstrap.Modal.getInstance(document.getElementById('rubricModal')).hide();
                _reloadRubricsTable();
            } else {
                // Mostrar errores de validación dentro del modal
                const errContainer = document.getElementById('rubricFormErrors');
                if (errContainer) {
                    errContainer.innerHTML = Object.entries(data.errors || {})
                        .map(([field, msgs]) => `<div class="text-danger small">${field}: ${msgs.join(', ')}</div>`)
                        .join('');
                }
            }
        })
        .catch(err => console.error('[RubricModal] Error al guardar:', err));
}

// ── Recarga solo el bloque de la tabla sin full-reload ────────────────────
function _reloadRubricsTable() {
    const tableContainer = document.getElementById('rubricsTableContainer');
    if (!tableContainer) {
        window.location.reload();
        return;
    }
    fetch(window.location.href, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(res => res.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newTable = doc.getElementById('rubricsTableContainer');
            if (newTable) tableContainer.innerHTML = newTable.innerHTML;
        });
}