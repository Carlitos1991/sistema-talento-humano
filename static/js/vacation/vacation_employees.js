// ===========================
// VARIABLES GLOBALES
// ===========================
let currentPage = 1;
let totalPages = 1;

// ===========================
// INICIALIZACIÓN
// ===========================
document.addEventListener('DOMContentLoaded', function () {
    initializePagination();
    initializeSearch();
});

function initializePagination() {
    if (window.initialPagination) {
        currentPage = window.initialPagination.current_page;
        totalPages = window.initialPagination.total_pages;
    }

    // Eventos de botones de paginación
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');

    if (btnPrev) {
        btnPrev.addEventListener('click', function () {
            if (currentPage > 1) {
                loadPage(currentPage - 1);
            }
        });
    }

    if (btnNext) {
        btnNext.addEventListener('click', function () {
            if (currentPage < totalPages) {
                loadPage(currentPage + 1);
            }
        });
    }
}

function initializeSearch() {
    const searchInput = document.getElementById('table-search');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function () {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                currentPage = 1; // Reset a página 1 al buscar
                loadPage(1);
            }, 500);
        });
    }
}

// ===========================
// CARGA DE DATOS VÍA AJAX
// ===========================
function loadPage(page) {
    const searchQuery = document.getElementById('table-search').value;
    const urlList = document.getElementById('url-list').value;
    const csrfToken = document.getElementById('csrf-token').value;

    const url = `${urlList}?page=${page}&q=${encodeURIComponent(searchQuery)}`;

    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrfToken
        }
    })
        .then(response => response.json())
        .then(data => {
            // Actualizar tabla
            document.getElementById('table-content-wrapper').innerHTML = data.html;

            // Actualizar paginación
            if (data.pagination) {
                currentPage = data.pagination.current_page;
                totalPages = data.pagination.total_pages;

                updatePaginationUI(data.pagination);
            }
        })
        .catch(error => {
            console.error('Error:', error);
        });
}

function updatePaginationUI(pagination) {
    const pageInfo = document.getElementById('page-info');
    const currentPageDisplay = document.getElementById('current-page-display');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');

    if (pageInfo) {
        pageInfo.textContent = `Mostrando ${pagination.start_index} a ${pagination.end_index} de ${pagination.total_count}`;
    }

    if (currentPageDisplay) {
        currentPageDisplay.textContent = pagination.current_page;
    }

    if (btnPrev) {
        btnPrev.disabled = !pagination.has_previous;
    }

    if (btnNext) {
        btnNext.disabled = !pagination.has_next;
    }
}

// ===========================
// FUNCIONES PARA VACACIONES
// ===========================
function createFirstVacation(employeeId) {
    const modal = document.getElementById('vacationModal');
    const modalContent = document.getElementById('vacation-modal-content');
    const url = `/vacation/requests/create-first/${employeeId}/`;
    
    fetch(url)
        .then(response => {
            if (!response.ok) throw new Error('Error de red');
            return response.text();
        })
        .then(html => {
            modalContent.innerHTML = html;
            modal.classList.remove('hidden');
            
            // Botones de cerrar
            const closeButtons = modalContent.querySelectorAll('.js-close-modal-vacation');
            closeButtons.forEach(btn => {
                btn.onclick = function (e) {
                    e.preventDefault();
                    closeVacationModal();
                };
            });
            
            // Cerrar al hacer click fuera
            modal.onclick = function (event) {
                if (event.target === modal) {
                    closeVacationModal();
                }
            };
            
            // Adjuntar submit del formulario
            attachFirstVacationFormSubmit();
        })
        .catch(error => console.error('Error cargando modal:', error));
}

function closeVacationModal() {
    const modal = document.getElementById('vacationModal');
    modal.classList.add('hidden');
    setTimeout(() => {
        document.getElementById('vacation-modal-content').innerHTML = '';
    }, 200);
}

function attachFirstVacationFormSubmit() {
    const form = document.getElementById('firstVacationForm');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        
        // Deshabilitar botón
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        
        // Limpiar errores previos
        document.querySelectorAll('.field-errors').forEach(el => el.innerHTML = '');
        document.querySelectorAll('.form-control').forEach(el => el.classList.remove('is-invalid'));
        
        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Cerrar modal y redirigir
                closeVacationModal();
                window.location.href = data.redirect_url;
            } else {
                // Limpiar errores anteriores
                document.querySelectorAll('.field-errors').forEach(el => el.innerHTML = '');
                document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
                
                // Mostrar errores
                if (data.errors) {
                    for (const [field, errors] of Object.entries(data.errors)) {
                        // Marcar el campo como inválido
                        const inputField = document.querySelector(`[name="${field}"]`);
                        if (inputField) {
                            inputField.classList.add('is-invalid');
                        }
                        
                        // Mostrar el mensaje de error
                        const errorDiv = document.getElementById(`error-${field}`);
                        if (errorDiv) {
                            errorDiv.innerHTML = errors.map(err => 
                                `<span class="text-danger"><i class="fas fa-exclamation-circle"></i> ${err}</span>`
                            ).join('<br>');
                        }
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        });
    });
}

function openVacationModal(employeeId) {
    // Redirigir a la página de detalle de vacaciones
    window.location.href = `/vacation/requests/employee/${employeeId}/`;
}
