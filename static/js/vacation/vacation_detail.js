// Abrir modal de nueva vacación
function openNewVacationModal(employeeId) {
    const modal = document.getElementById('modalNewVacation');
    const url = `/vacation/requests/create-new/${employeeId}/`;
    
    fetch(url)
        .then(response => response.text())
        .then(html => {
            modal.innerHTML = html;
            modal.classList.remove('hidden');
            document.body.classList.add('modal-open'); // Bloquear scroll
            attachNewVacationFormSubmit();
            attachCloseModalEvents();
        })
        .catch(error => {
            console.error('Error al cargar el modal:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al cargar el formulario',
                confirmButtonColor: '#3085d6'
            });
        });
}

// Manejar envío del formulario
function attachNewVacationFormSubmit() {
    const form = document.getElementById('newVacationForm');
    if (!form) return;

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creando...';

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect_url;
            } else {
                // Limpiar errores anteriores
                document.querySelectorAll('.field-errors').forEach(el => el.innerHTML = '');
                document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                
                if (data.errors) {
                    for (const [field, errors] of Object.entries(data.errors)) {
                        // Marcar el campo como inválido
                        const fieldElement = document.querySelector(`[name="${field}"]`);
                        if (fieldElement) {
                            fieldElement.classList.add('is-invalid');
                        }
                        
                        // Mostrar el error
                        const errorDiv = document.getElementById(`error-${field}`);
                        if (errorDiv) {
                            errorDiv.innerHTML = errors.map(err => 
                                `<span class="text-danger"><i class="fas fa-exclamation-circle"></i> ${err}</span>`
                            ).join('<br>');
                        }
                    }
                }
                
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-plane"></i> CREAR NUEVO PERÍODO';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al crear el período de vacaciones',
                confirmButtonColor: '#3085d6'
            });
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-plane"></i> CREAR NUEVO PERÍODO';
        });
    });
}

// Cerrar modal
function attachCloseModalEvents() {
    const modal = document.getElementById('modalNewVacation');
    const closeBtns = document.querySelectorAll('.js-close-modal-new-vacation');
    
    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modal.classList.add('hidden');
            modal.innerHTML = '';
            document.body.classList.remove('modal-open'); // Desbloquear scroll
        });
    });

    // Cerrar al hacer clic fuera del modal
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.innerHTML = '';
            document.body.classList.remove('modal-open'); // Desbloquear scroll
        }
    });
}

// Funcionalidad de búsqueda
function initializeSearchFunctionality() {
    const searchInput = document.getElementById('table-search');
    const searchHidden = document.getElementById('search-hidden');
    const searchForm = document.getElementById('searchForm');
    
    if (!searchInput || !searchHidden || !searchForm) return;
    
    // Sincronizar búsqueda
    searchInput.addEventListener('input', function(e) {
        searchHidden.value = e.target.value;
    });
    
    // Submit al presionar Enter
    searchInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            searchForm.submit();
        }
    });
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    initializeSearchFunctionality();
});

// Abrir modal de permiso por horas
function openHourPermitModal(employeeId) {
    const modal = document.getElementById('modalHourPermit');
    const url = `/vacation/requests/create-hour-permit/${employeeId}/`;
    
    fetch(url)
        .then(response => response.text())
        .then(html => {
            modal.innerHTML = html;
            modal.classList.remove('hidden');
            document.body.classList.add('modal-open'); // Bloquear scroll
            attachHourPermitFormSubmit();
            attachHourPermitCloseEvents();
        })
        .catch(error => {
            console.error('Error al cargar el modal:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al cargar el formulario',
                confirmButtonColor: '#3085d6'
            });
        });
}

// Manejar envío del formulario de permiso por horas
function attachHourPermitFormSubmit() {
    const form = document.getElementById('hourPermitForm');
    if (!form) return;

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creando...';

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect_url;
            } else {
                // Limpiar errores anteriores
                document.querySelectorAll('.field-errors').forEach(el => el.innerHTML = '');
                document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                
                if (data.errors) {
                    for (const [field, errors] of Object.entries(data.errors)) {
                        // Marcar el campo como inválido
                        const fieldElement = document.querySelector(`[name="${field}"]`);
                        if (fieldElement) {
                            fieldElement.classList.add('is-invalid');
                        }
                        
                        // Mostrar el error
                        const errorDiv = document.getElementById(`error-${field}`);
                        if (errorDiv) {
                            errorDiv.innerHTML = errors.map(err => 
                                `<span class="text-danger"><i class="fas fa-exclamation-circle"></i> ${err}</span>`
                            ).join('<br>');
                        }
                    }
                }
                
                // Mostrar mensaje general con SweetAlert2 si existe
                if (data.message) {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: data.message,
                        confirmButtonColor: '#dc3545'
                    });
                }
                
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-check-circle"></i> CREAR PERMISO';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al crear el permiso',
                confirmButtonColor: '#3085d6'
            });
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-check-circle"></i> CREAR PERMISO';
        });
    });
}

// Cerrar modal de permiso por horas
function attachHourPermitCloseEvents() {
    const modal = document.getElementById('modalHourPermit');
    const closeBtns = document.querySelectorAll('.js-close-modal-hour-permit');
    
    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modal.classList.add('hidden');
            modal.innerHTML = '';
            document.body.classList.remove('modal-open'); // Desbloquear scroll
        });
    });

    // Cerrar al hacer clic fuera del modal
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.innerHTML = '';
            document.body.classList.remove('modal-open'); // Desbloquear scroll
        }
    });
}

// Abrir modal de permiso por días
function openDayPermitModal(employeeId) {
    const modal = document.getElementById('modalDayPermit');
    const url = `/vacation/requests/create-day-permit/${employeeId}/`;
    
    fetch(url)
        .then(response => response.text())
        .then(html => {
            modal.innerHTML = html;
            modal.classList.remove('hidden');
            document.body.classList.add('modal-open'); // Bloquear scroll
            attachDayPermitFormSubmit();
            attachDayPermitCloseEvents();
        })
        .catch(error => {
            console.error('Error al cargar el modal:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al cargar el formulario',
                confirmButtonColor: '#3085d6'
            });
        });
}

// Manejar envío del formulario de permiso por días
function attachDayPermitFormSubmit() {
    const form = document.getElementById('dayPermitForm');
    if (!form) return;

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creando...';

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': formData.get('csrfmiddlewaretoken')
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.location.href = data.redirect_url;
            } else {
                document.querySelectorAll('.field-errors').forEach(el => el.innerHTML = '');
                document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                
                if (data.errors) {
                    for (const [field, errors] of Object.entries(data.errors)) {
                        const fieldElement = document.querySelector(`[name="${field}"]`);
                        if (fieldElement) {
                            fieldElement.classList.add('is-invalid');
                        }
                        
                        const errorDiv = document.getElementById(`error-${field}`);
                        if (errorDiv) {
                            errorDiv.innerHTML = errors.map(err => 
                                `<span class="text-danger"><i class="fas fa-exclamation-circle"></i> ${err}</span>`
                            ).join('<br>');
                        }
                    }
                }
                
                if (data.message) {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: data.message,
                        confirmButtonColor: '#dc3545'
                    });
                }
                
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-save"></i> Crear Permiso';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al crear el permiso',
                confirmButtonColor: '#3085d6'
            });
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-save"></i> Crear Permiso';
        });
    });
}

// Cerrar modal de permiso por días
function attachDayPermitCloseEvents() {
    const modal = document.getElementById('modalDayPermit');
    const closeBtns = modal.querySelectorAll('.js-close-modal-day-permit, .btn-cancel');
    
    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modal.classList.add('hidden');
            modal.innerHTML = '';
            document.body.classList.remove('modal-open'); // Desbloquear scroll
        });
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.innerHTML = '';
            document.body.classList.remove('modal-open'); // Desbloquear scroll
        }
    });
}

// Abrir modal de listado de permisos
function openPermitListModal(employeeId) {
    const modal = document.getElementById('modalPermitList');
    const url = `/vacation/requests/permit-list/${employeeId}/`;
    
    fetch(url)
        .then(response => response.text())
        .then(html => {
            modal.innerHTML = html;
            modal.classList.remove('hidden');
            document.body.classList.add('modal-open'); // Bloquear scroll
            attachPermitListCloseEvents();
            attachPermitSearchEvents(employeeId);
        })
        .catch(error => {
            console.error('Error al cargar el modal:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al cargar la lista de permisos',
                confirmButtonColor: '#3085d6'
            });
        });
}

// Cargar página específica de permisos
function loadPermitPage(pageNumber) {
    const modal = document.getElementById('modalPermitList');
    const searchInput = document.getElementById('permitSearchInput');
    const searchQuery = searchInput ? searchInput.value : '';
    const employeeId = modal.getAttribute('data-employee-id');
    
    let url = `/vacation/requests/permit-list/${employeeId}/?page=${pageNumber}`;
    if (searchQuery) {
        url += `&search=${encodeURIComponent(searchQuery)}`;
    }
    
    fetch(url)
        .then(response => response.text())
        .then(html => {
            modal.innerHTML = html;
            attachPermitListCloseEvents();
            attachPermitSearchEvents(employeeId);
        })
        .catch(error => {
            console.error('Error al cargar la página:', error);
        });
}

// Limpiar búsqueda de permisos
function clearPermitSearch() {
    const searchInput = document.getElementById('permitSearchInput');
    if (searchInput) {
        searchInput.value = '';
        const modal = document.getElementById('modalPermitList');
        const employeeId = modal.getAttribute('data-employee-id');
        loadPermitPage(1);
    }
}

// Adjuntar eventos de búsqueda
function attachPermitSearchEvents(employeeId) {
    const modal = document.getElementById('modalPermitList');
    modal.setAttribute('data-employee-id', employeeId);
    
    const searchInput = document.getElementById('permitSearchInput');
    
    if (searchInput) {
        // Búsqueda en tiempo real con debounce
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                loadPermitPage(1);
            }, 500);
        });
    }
}

// Cerrar modal de listado de permisos
function attachPermitListCloseEvents() {
    const modal = document.getElementById('modalPermitList');
    const closeBtns = modal.querySelectorAll('.js-close-modal-permit-list');
    
    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modal.classList.add('hidden');
            modal.innerHTML = '';
            document.body.classList.remove('modal-open'); // Desbloquear scroll
        });
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.innerHTML = '';
            document.body.classList.remove('modal-open'); // Desbloquear scroll
        }
    });
}

// Funciones para aprobar/rechazar permisos
function approvePermit(permitId) {
    Swal.fire({
        title: '¿Aprobar permiso?',
        text: '¿Está seguro de aprobar este permiso? Se descontará del balance de vacaciones.',
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: '#28a745',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, aprobar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            // Llamar a la vista de aprobación
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            fetch(`/vacation/requests/approve-permit/${permitId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Aprobado!',
                        text: data.message,
                        confirmButtonColor: '#28a745'
                    }).then(() => {
                        window.location.reload();
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: data.message,
                        confirmButtonColor: '#dc3545'
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Error al aprobar el permiso',
                    confirmButtonColor: '#dc3545'
                });
            });
        }
    });
}

function rejectPermit(permitId) {
    Swal.fire({
        title: '¿Rechazar permiso?',
        text: '¿Está seguro de rechazar este permiso?',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, rechazar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            // Mostrar loading
            Swal.fire({
                title: 'Procesando...',
                text: 'Rechazando permiso',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
            
            // Llamar a la vista de rechazo
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            fetch(`/vacation/requests/reject-permit/${permitId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Rechazado',
                        text: data.message,
                        confirmButtonColor: '#3085d6'
                    }).then(() => {
                        window.location.reload();
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: data.message,
                        confirmButtonColor: '#dc3545'
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Error al rechazar el permiso',
                    confirmButtonColor: '#dc3545'
                });
            });
        }
    });
}

function cancelPermit(permitId) {
    Swal.fire({
        title: '¿Anular permiso?',
        text: '¿Está seguro de anular este permiso? Si ya estaba aprobado, se revertirá el descuento.',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#6c757d',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Sí, anular',
        cancelButtonText: 'No anular'
    }).then((result) => {
        if (result.isConfirmed) {
            // Mostrar loading
            Swal.fire({
                title: 'Procesando...',
                text: 'Anulando permiso',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
            
            // Llamar a la vista de anulación
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            fetch(`/vacation/requests/cancel-permit/${permitId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Anulado',
                        text: data.message,
                        confirmButtonColor: '#3085d6'
                    }).then(() => {
                        window.location.reload();
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: data.message,
                        confirmButtonColor: '#dc3545'
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Error al anular el permiso',
                    confirmButtonColor: '#dc3545'
                });
            });
        }
    });
}


// ============================================================================
// FUNCIONES PARA LIQUIDACIÓN DE VACACIONES
// ============================================================================

/**
 * Abrir modal para crear liquidación de vacaciones
 */
function openLiquidationModal(employeeId) {
    fetch(`/vacation/requests/create-liquidation/${employeeId}/`)
        .then(response => response.text())
        .then(html => {
            // Crear contenedor para el modal si no existe
            let modalContainer = document.getElementById('liquidationModalContainer');
            if (!modalContainer) {
                modalContainer = document.createElement('div');
                modalContainer.id = 'liquidationModalContainer';
                document.body.appendChild(modalContainer);
            }
            
            // Insertar HTML del modal
            modalContainer.innerHTML = html;
            
            // Bloquear scroll del body
            document.body.classList.add('modal-open');
            
            // Adjuntar eventos al formulario
            attachLiquidationFormSubmit(employeeId);
            
            // Adjuntar eventos a los campos de fecha para calcular días
            attachDateChangeListeners();
            
            // Mostrar modal
            const overlay = document.getElementById('liquidationModalOverlay');
            if (overlay) {
                overlay.style.display = 'flex';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudo cargar el formulario de liquidación',
                confirmButtonColor: '#dc3545'
            });
        });
}

/**
 * Cerrar modal de liquidación
 */
function closeLiquidationModal() {
    const overlay = document.getElementById('liquidationModalOverlay');
    if (overlay) {
        overlay.style.display = 'none';
        overlay.remove();
    }
    // Desbloquear scroll del body
    document.body.classList.remove('modal-open');
}

/**
 * Adjuntar eventos a los campos de fecha para calcular días automáticamente
 */
function attachDateChangeListeners() {
    const startDateInput = document.getElementById('id_start_date');
    const endDateInput = document.getElementById('id_end_date');
    const daysCounter = document.getElementById('daysCounter');
    const calculatedDaysSpan = document.getElementById('calculatedDays');
    
    if (!startDateInput || !endDateInput) return;
    
    const calculateDays = () => {
        const startDate = startDateInput.value;
        const endDate = endDateInput.value;
        
        if (startDate && endDate) {
            const start = new Date(startDate);
            const end = new Date(endDate);
            
            if (end >= start) {
                // Calcular días: diferencia + 1 (inclusivo)
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
    
    startDateInput.addEventListener('change', calculateDays);
    endDateInput.addEventListener('change', calculateDays);
}

/**
 * Adjuntar evento submit al formulario de liquidación
 */
function attachLiquidationFormSubmit(employeeId) {
    const form = document.getElementById('liquidationForm');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(`/vacation/requests/create-liquidation/${employeeId}/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Éxito!',
                    text: data.message,
                    confirmButtonColor: '#28a745'
                }).then(() => {
                    closeLiquidationModal();
                    window.location.reload();
                });
            } else {
                // Mostrar errores del formulario
                if (data.message) {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: data.message,
                        confirmButtonColor: '#dc3545'
                    });
                }
                
                // Mostrar errores específicos de campos
                if (data.errors) {
                    const errors = JSON.parse(data.errors);
                    for (const field in errors) {
                        const errorDiv = document.getElementById(`${field}_error`);
                        if (errorDiv) {
                            errorDiv.textContent = errors[field][0].message;
                            errorDiv.style.display = 'block';
                        }
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al crear la solicitud de liquidación',
                confirmButtonColor: '#dc3545'
            });
        });
    });
}


// ============================================================================
// FUNCIONES PARA LISTADO DE LIQUIDACIONES
// ============================================================================

/**
 * Abrir modal de listado de liquidaciones
 */
function openLiquidationListModal(employeeId) {
    fetch(`/vacation/requests/liquidation-list/${employeeId}/`)
        .then(response => response.text())
        .then(html => {
            let modalContainer = document.getElementById('liquidationListModalContainer');
            if (!modalContainer) {
                modalContainer = document.createElement('div');
                modalContainer.id = 'liquidationListModalContainer';
                document.body.appendChild(modalContainer);
            }
            
            modalContainer.innerHTML = html;
            
            // Adjuntar eventos de búsqueda
            attachLiquidationSearchEvents(employeeId);
            
            const overlay = document.getElementById('liquidationListModalOverlay');
            if (overlay) {
                overlay.style.display = 'flex';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudo cargar el listado de liquidaciones',
                confirmButtonColor: '#dc3545'
            });
        });
}

/**
 * Cerrar modal de listado de liquidaciones
 */
function closeLiquidationListModal() {
    const overlay = document.getElementById('liquidationListModalOverlay');
    if (overlay) {
        overlay.style.display = 'none';
        overlay.remove();
    }
    // Desbloquear scroll del body
    document.body.classList.remove('modal-open');
}

/**
 * Cargar página de liquidaciones
 */
function loadLiquidationPage(pageNumber) {
    const employeeId = document.getElementById('liquidationSearchInput').getAttribute('data-employee-id');
    const searchQuery = document.getElementById('liquidationSearchInput').value;
    
    let url = `/vacation/requests/liquidation-list/${employeeId}/?page=${pageNumber}`;
    if (searchQuery) {
        url += `&search=${encodeURIComponent(searchQuery)}`;
    }
    
    fetch(url)
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const newContent = doc.querySelector('.modal-body').innerHTML;
            
            const modalBody = document.querySelector('#liquidationListModalOverlay .modal-body');
            if (modalBody) {
                modalBody.innerHTML = newContent;
                attachLiquidationSearchEvents(employeeId);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

/**
 * Adjuntar eventos de búsqueda para liquidaciones
 */
function attachLiquidationSearchEvents(employeeId) {
    const searchInput = document.getElementById('liquidationSearchInput');
    if (!searchInput) return;
    
    searchInput.setAttribute('data-employee-id', employeeId);
    
    let debounceTimer;
    searchInput.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            loadLiquidationPage(1);
        }, 500);
    });
    
    // Adjuntar eventos de impresión a todos los botones
    const printButtons = document.querySelectorAll('.js-print-action');
    printButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const actionId = this.getAttribute('data-action-id');
            printLiquidationPDF(actionId);
        });
    });
}

/**
 * Imprimir PDF de liquidación
 */
function printLiquidationPDF(actionId) {
    const pdfUrl = `/personnel_actions/${actionId}/pdf/`;
    window.open(pdfUrl, '_blank');
}

/**
 * Registrar liquidación
 */
function registerLiquidation(actionId) {
    Swal.fire({
        title: '¿Registrar liquidación?',
        text: 'Esta acción creará el historial de vacaciones y descontará del balance',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#28a745',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Sí, registrar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            Swal.fire({
                title: 'Procesando...',
                text: 'Registrando liquidación',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
            
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            fetch(`/vacation/requests/register-liquidation/${actionId}/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    Swal.fire({
                        icon: 'success',
                        title: '¡Registrada!',
                        text: data.message,
                        confirmButtonColor: '#28a745'
                    }).then(() => {
                        window.location.reload();
                    });
                } else {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: data.message,
                        confirmButtonColor: '#dc3545'
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                Swal.fire({
                    icon: 'error',
                    title: 'Error',
                    text: 'Error al registrar la liquidación',
                    confirmButtonColor: '#dc3545'
                });
            });
        }
    });
}

/**
 * Editar liquidación
 */
function editLiquidation(actionId) {
    fetch(`/vacation/requests/edit-liquidation/${actionId}/`)
        .then(response => response.text())
        .then(html => {
            let modalContainer = document.getElementById('liquidationEditModalContainer');
            if (!modalContainer) {
                modalContainer = document.createElement('div');
                modalContainer.id = 'liquidationEditModalContainer';
                document.body.appendChild(modalContainer);
            }
            
            modalContainer.innerHTML = html;
            
            // Bloquear scroll del body
            document.body.classList.add('modal-open');
            
            // Adjuntar eventos
            attachLiquidationEditFormSubmit(actionId);
            attachDateChangeListenersEdit();
            
            // Calcular días iniciales
            calculateDaysEdit();
            
            const overlay = document.getElementById('liquidationEditModalOverlay');
            if (overlay) {
                overlay.style.display = 'flex';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudo cargar el formulario de edición',
                confirmButtonColor: '#dc3545'
            });
        });
}

/**
 * Cerrar modal de edición
 */
function closeLiquidationEditModal() {
    const overlay = document.getElementById('liquidationEditModalOverlay');
    if (overlay) {
        overlay.style.display = 'none';
        overlay.remove();
    }
    // Desbloquear scroll del body
    document.body.classList.remove('modal-open');
}

/**
 * Adjuntar eventos de cambio de fecha para edición
 */
function attachDateChangeListenersEdit() {
    const startDateInput = document.getElementById('id_start_date');
    const endDateInput = document.getElementById('id_end_date');
    
    if (!startDateInput || !endDateInput) return;
    
    startDateInput.addEventListener('change', calculateDaysEdit);
    endDateInput.addEventListener('change', calculateDaysEdit);
}

/**
 * Calcular días para edición
 */
function calculateDaysEdit() {
    const startDateInput = document.getElementById('id_start_date');
    const endDateInput = document.getElementById('id_end_date');
    const daysCounter = document.getElementById('daysCounterEdit');
    const calculatedDaysSpan = document.getElementById('calculatedDaysEdit');
    
    if (!startDateInput || !endDateInput) return;
    
    const startDate = startDateInput.value;
    const endDate = endDateInput.value;
    
    if (startDate && endDate) {
        const start = new Date(startDate);
        const end = new Date(endDate);
        
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
}

/**
 * Adjuntar submit al formulario de edición
 */
function attachLiquidationEditFormSubmit(actionId) {
    const form = document.getElementById('liquidationEditForm');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        Swal.fire({
            title: 'Procesando...',
            text: 'Guardando cambios',
            allowOutsideClick: false,
            didOpen: () => {
                Swal.showLoading();
            }
        });
        
        const formData = new FormData(form);
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        
        fetch(`/vacation/requests/edit-liquidation/${actionId}/`, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: '¡Éxito!',
                    text: data.message,
                    confirmButtonColor: '#28a745'
                }).then(() => {
                    closeLiquidationEditModal();
                    window.location.reload();
                });
            } else {
                if (data.message) {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: data.message,
                        confirmButtonColor: '#dc3545'
                    });
                }
                
                if (data.errors) {
                    const errors = JSON.parse(data.errors);
                    for (const field in errors) {
                        const errorDiv = document.getElementById(`${field}_error`);
                        if (errorDiv) {
                            errorDiv.textContent = errors[field][0].message;
                            errorDiv.style.display = 'block';
                        }
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al guardar los cambios',
                confirmButtonColor: '#dc3545'
            });
        });
    });
}

/**
 * Imprimir liquidación (por implementar)
 */
function printLiquidation(actionId) {
    // Abrir PDF en nueva ventana
    const url = `/vacation/requests/liquidation-print-pdf/${actionId}/`;
    window.open(url, '_blank');
}


/**
 * Abrir modal de historial de liquidaciones de vacaciones
 */
function openVacationHistoryModal(balanceId) {
    fetch(`/vacation/requests/vacation-history/${balanceId}/`)
        .then(response => response.text())
        .then(html => {
            let modalContainer = document.getElementById('vacationHistoryModalContainer');
            if (!modalContainer) {
                modalContainer = document.createElement('div');
                modalContainer.id = 'vacationHistoryModalContainer';
                document.body.appendChild(modalContainer);
            } else if (modalContainer.parentElement !== document.body) {
                // Si existe dentro del flujo del documento (p.ej. dentro del tab), moverlo al <body>
                document.body.appendChild(modalContainer);
            }

            // Insertar el HTML una vez el contenedor esté en el <body>
            modalContainer.innerHTML = html;
            
            // Bloquear scroll del body
            document.body.classList.add('modal-open');
            
            const overlay = document.getElementById('vacationHistoryModalOverlay');
            if (overlay) {
                overlay.style.display = 'flex';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudo cargar el historial de liquidaciones',
                confirmButtonColor: '#dc3545'
            });
        });
}

/**
 * Cerrar modal de historial de liquidaciones
 */
function closeVacationHistoryModal() {
    const overlay = document.getElementById('vacationHistoryModalOverlay');
    if (overlay) {
        overlay.style.display = 'none';
        overlay.remove();
    }
    document.body.classList.remove('modal-open');
}

/**
 * Abrir modal de historial de permisos
 */
function openPermitHistoryModal(balanceId) {
    fetch(`/vacation/requests/permit-history/${balanceId}/`)
        .then(response => response.text())
        .then(html => {
            let modalContainer = document.getElementById('permitHistoryModalContainer');
            if (!modalContainer) {
                modalContainer = document.createElement('div');
                modalContainer.id = 'permitHistoryModalContainer';
                document.body.appendChild(modalContainer);
            } else if (modalContainer.parentElement !== document.body) {
                // Mover al body para evitar render dentro de otros contenedores
                document.body.appendChild(modalContainer);
            }

            modalContainer.innerHTML = html;
            
            // Bloquear scroll del body
            document.body.classList.add('modal-open');
            
            const overlay = document.getElementById('permitHistoryModalOverlay');
            if (overlay) {
                overlay.style.display = 'flex';
            }
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'No se pudo cargar el historial de permisos',
                confirmButtonColor: '#dc3545'
            });
        });
}

/**
 * Cerrar modal de historial de permisos
 */
function closePermitHistoryModal() {
    const overlay = document.getElementById('permitHistoryModalOverlay');
    if (overlay) {
        overlay.style.display = 'none';
        overlay.remove();
    }
    document.body.classList.remove('modal-open');
}


// ==========================================
// REPORTE DE PERMISOS
// ==========================================
function openPermitReportModal() {
    const employeeId = document.querySelector('[data-employee-id]').dataset.employeeId;
    
    fetch(`/vacation/requests/permit-report-modal/${employeeId}/`)
        .then(response => response.text())
        .then(html => {
            const container = document.getElementById('permitReportModalContainer');
            container.innerHTML = html;
            
            // Mostrar overlay
            const overlay = document.getElementById('permitReportModalOverlay');
            overlay.style.display = 'flex';
            
            // Bloquear scroll del fondo
            document.body.classList.add('modal-open');
            
            // Configurar fechas por defecto (último año)
            const today = new Date();
            const lastYear = new Date();
            lastYear.setFullYear(today.getFullYear() - 1);
            
            document.getElementById('reportEndDate').valueAsDate = today;
            document.getElementById('reportStartDate').valueAsDate = lastYear;
        })
        .catch(error => {
            console.error('Error:', error);
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: 'Error al cargar el formulario de reporte'
            });
        });
}

function closePermitReportModal() {
    const overlay = document.getElementById('permitReportModalOverlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
    
    // Restaurar scroll del fondo
    document.body.classList.remove('modal-open');
    
    // Limpiar contenedor
    const container = document.getElementById('permitReportModalContainer');
    if (container) {
        container.innerHTML = '';
    }
}
