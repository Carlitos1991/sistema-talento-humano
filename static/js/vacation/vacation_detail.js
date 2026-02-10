// Abrir modal de nueva vacación
function openNewVacationModal(employeeId) {
    const modal = document.getElementById('modalNewVacation');
    const url = `/vacation/requests/create-new/${employeeId}/`;
    
    fetch(url)
        .then(response => response.text())
        .then(html => {
            modal.innerHTML = html;
            modal.classList.remove('hidden');
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
        });
    });

    // Cerrar al hacer clic fuera del modal
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.innerHTML = '';
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
        });
    });

    // Cerrar al hacer clic fuera del modal
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.innerHTML = '';
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
        });
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.innerHTML = '';
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
            attachPermitListCloseEvents();
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

// Cerrar modal de listado de permisos
function attachPermitListCloseEvents() {
    const modal = document.getElementById('modalPermitList');
    const closeBtns = modal.querySelectorAll('.js-close-modal-permit-list');
    
    closeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            modal.classList.add('hidden');
            modal.innerHTML = '';
        });
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.add('hidden');
            modal.innerHTML = '';
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
            // Mostrar loading
            Swal.fire({
                title: 'Procesando...',
                text: 'Aprobando permiso',
                allowOutsideClick: false,
                didOpen: () => {
                    Swal.showLoading();
                }
            });
            
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


