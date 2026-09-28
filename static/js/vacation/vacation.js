/**
 * SIGETH - MÓDULO DE VACACIONES (CONSOLIDADO)
 * Totalmente integrado con main.js (openAjaxModal, submitAjaxForm, refreshCurrentTable, Swal)
 */
document.addEventListener('DOMContentLoaded', () => {

    /* =========================================================================
       1. BUSCADOR EN TIEMPO REAL - LISTADO PRINCIPAL (vacation_request_list)
       ========================================================================= */
    const searchInput = document.getElementById('table-search');
    if (searchInput) {
        let debounceTimer;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                const query = e.target.value.trim();
                const currentUrl = new URL(window.location.href);

                if (query) {
                    currentUrl.searchParams.set('q', query);
                } else {
                    currentUrl.searchParams.delete('q');
                }
                currentUrl.searchParams.set('page', 1);

                window.history.pushState({}, '', currentUrl.toString());

                if (typeof window.refreshCurrentTable === 'function') {
                    window.refreshCurrentTable({q: query, page: 1});
                }
            }, 350);
        });
    }

    /* =========================================================================
       2. BUSCADOR - DETALLE DE VACACIONES (employee_vacation_detail)
       ========================================================================= */
    const detailSearch = document.getElementById('vacationDetailSearch');
    if (detailSearch) {
        detailSearch.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const query = detailSearch.value.trim();
                const url = new URL(window.location.href);
                if (query) {
                    url.searchParams.set('search', query);
                } else {
                    url.searchParams.delete('search');
                }
                url.searchParams.set('page', 1);
                window.location.href = url.toString();
            }
        });
    }

    /* =========================================================================
       3. NAVEGACIÓN MANUAL POR INPUT NUMÉRICO DE PÁGINA
       ========================================================================= */
    const handlePageInput = (inputEl) => {
        let pageVal = parseInt(inputEl.value, 10);
        const maxPage = parseInt(inputEl.dataset.maxPage || 1, 10);

        if (isNaN(pageVal) || pageVal < 1) pageVal = 1;
        if (pageVal > maxPage) pageVal = maxPage;

        inputEl.value = pageVal;

        const currentUrl = new URL(window.location.href);
        currentUrl.searchParams.set('page', pageVal);
        window.history.pushState({}, '', currentUrl.toString());

        if (typeof window.refreshCurrentTable === 'function') {
            window.refreshCurrentTable({page: pageVal});
        }
    };

    document.addEventListener('change', (e) => {
        if (e.target.matches('.page-input')) {
            handlePageInput(e.target);
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.target.matches('.page-input') && e.key === 'Enter') {
            e.preventDefault();
            handlePageInput(e.target);
        }
    });

    /* =========================================================================
       4. GESTOR UNIVERSAL DE MODALES (LISTADO Y DETALLE)
       ========================================================================= */
    document.addEventListener('click', (e) => {
        // A) Botones o enlaces de apertura de modal
        const btnModal = e.target.closest('.btn-vacation-action, .btn-vacation-modal, [data-modal-url]');
        if (btnModal) {
            e.preventDefault();
            const targetUrl = btnModal.dataset.url || btnModal.dataset.modalUrl;

            if (targetUrl && typeof window.openAjaxModal === 'function') {
                window.openAjaxModal(targetUrl, () => {
                    // Inicializar calculador de días si el modal contiene fechas
                    initModalDateCalculator();
                });
            }
            return;
        }

        // B) Botón Imprimir PDF Acción de Personal (Liquidación)
        const btnPrint = e.target.closest('.js-print-action');
        if (btnPrint) {
            e.preventDefault();
            const actionId = btnPrint.dataset.actionId;
            if (actionId) {
                window.open(`/vacation/requests/liquidation-print-pdf/${actionId}/`, '_blank');
            }
            return;
        }

        // C) Botones de Aprobar, Rechazar o Anular Permisos
        const btnApprove = e.target.closest('.btn-approve-permit');
        if (btnApprove) {
            e.preventDefault();
            handlePermitAction(btnApprove.dataset.id, 'approve');
            return;
        }

        const btnReject = e.target.closest('.btn-reject-permit');
        if (btnReject) {
            e.preventDefault();
            handlePermitAction(btnReject.dataset.id, 'reject');
            return;
        }

        const btnCancel = e.target.closest('.btn-cancel-permit');
        if (btnCancel) {
            e.preventDefault();
            handlePermitAction(btnCancel.dataset.id, 'cancel');
            return;
        }

        // D) Botón Registrar Liquidación
        const btnRegisterLiq = e.target.closest('.btn-register-liquidation');
        if (btnRegisterLiq) {
            e.preventDefault();
            handleRegisterLiquidation(btnRegisterLiq.dataset.id);
        }
    });

    /* =========================================================================
       5. ENVÍO AJAX DE FORMULARIOS DENTRO DE MODALES
       ========================================================================= */
    document.addEventListener('submit', (e) => {
        const form = e.target;
        if (form.matches('#firstVacationForm, #newVacationForm, #periodForm, #hourPermitForm, #dayPermitForm, #liquidationForm, #liquidationEditForm, .ajax-vacation-form')) {
            if (typeof window.submitAjaxForm === 'function') {
                window.submitAjaxForm(e, (data) => {
                    // Si el servidor envía URL de redirección, redirigir
                    if (data && data.redirect_url) {
                        window.location.href = data.redirect_url;
                        return;
                    }
                    // Si estamos en el listado principal, refrescar tabla
                    if (typeof window.refreshCurrentTable === 'function' && document.getElementById('table-content-wrapper')) {
                        window.refreshCurrentTable();
                    } else {
                        // En la vista de detalle recargamos para actualizar balances
                        window.location.reload();
                    }
                });
            }
        }
    });

});

/* =============================================================================
   6. FUNCIONES AUXILIARES (APROBACIONES, REGISTROS Y CÁLCULOS DE MODAL)
   ============================================================================= */

// Aprobación, rechazo y anulación con SweetAlert2 de main.js
function handlePermitAction(permitId, action) {
    if (!permitId) return;

    const configs = {
        'approve': {
            title: '¿Aprobar permiso?',
            text: 'Se descontará del balance de vacaciones del empleado.',
            icon: 'question',
            confirmText: 'Sí, aprobar',
            url: `/vacation/requests/approve-permit/${permitId}/`
        },
        'reject': {
            title: '¿Rechazar permiso?',
            text: 'El permiso pasará a estado Rechazado.',
            icon: 'warning',
            confirmText: 'Sí, rechazar',
            url: `/vacation/requests/reject-permit/${permitId}/`
        },
        'cancel': {
            title: '¿Anular permiso?',
            text: 'Si ya estaba aprobado, se revertirá el descuento en el saldo.',
            icon: 'warning',
            confirmText: 'Sí, anular',
            url: `/vacation/requests/cancel-permit/${permitId}/`
        }
    };

    const cfg = configs[action];
    if (!cfg) return;

    Swal.fire({
        title: cfg.title,
        text: cfg.text,
        icon: cfg.icon,
        showCancelButton: true,
        confirmButtonText: cfg.confirmText,
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

            fetch(cfg.url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        if (typeof window.showToast === 'function') {
                            window.showToast(data.message || 'Operación completada', 'success');
                        }
                        setTimeout(() => window.location.reload(), 600);
                    } else {
                        Swal.fire({
                            icon: 'error',
                            title: 'Atención',
                            text: data.message || 'No se pudo procesar la solicitud.'
                        });
                    }
                })
                .catch(err => {
                    console.error(err);
                    Swal.fire({icon: 'error', title: 'Error', text: 'Error de comunicación con el servidor.'});
                });
        }
    });
}

// Registrar Liquidación de Vacaciones
function handleRegisterLiquidation(actionId) {
    if (!actionId) return;

    Swal.fire({
        title: '¿Registrar liquidación?',
        text: 'Esta acción creará el historial de vacaciones y descontará los días del balance.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, registrar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

            fetch(`/vacation/requests/register-liquidation/${actionId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        if (typeof window.showToast === 'function') {
                            window.showToast(data.message || 'Liquidación registrada con éxito', 'success');
                        }
                        setTimeout(() => window.location.reload(), 600);
                    } else {
                        Swal.fire({
                            icon: 'error',
                            title: 'Atención',
                            text: data.message || 'No se pudo registrar la liquidación.'
                        });
                    }
                })
                .catch(err => {
                    console.error(err);
                    Swal.fire({icon: 'error', title: 'Error', text: 'Error de comunicación con el servidor.'});
                });
        }
    });
}

// Calculador dinámico de días en formularios de modal (start_date y end_date)
function initModalDateCalculator() {
    const startInput = document.getElementById('id_start_date');
    const endInput = document.getElementById('id_end_date');
    const daysCounter = document.getElementById('daysCounter') || document.getElementById('daysCounterEdit');
    const calculatedDaysSpan = document.getElementById('calculatedDays') || document.getElementById('calculatedDaysEdit');

    if (!startInput || !endInput || !daysCounter || !calculatedDaysSpan) return;

    const calculate = () => {
        if (startInput.value && endInput.value) {
            const start = new Date(startInput.value);
            const end = new Date(endInput.value);
            if (end >= start) {
                const diffTime = Math.abs(end - start);
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
                calculatedDaysSpan.textContent = diffDays;
                daysCounter.style.display = 'flex';
            } else {
                daysCounter.style.display = 'none';
            }
        } else {
            daysCounter.style.display = 'none';
        }
    };

    startInput.addEventListener('change', calculate);
    endInput.addEventListener('change', calculate);
}