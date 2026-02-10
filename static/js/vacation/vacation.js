// ===========================
// ORDENAMIENTO DE TABLA
// ===========================
function sortTable(field) {
    const url = new URL(window.location.href);
    const currentOrder = url.searchParams.get('order_by');
    const currentDirection = url.searchParams.get('direction') || 'asc';
    
    // Si es el mismo campo, cambiar dirección
    if (currentOrder === field) {
        const newDirection = currentDirection === 'asc' ? 'desc' : 'asc';
        url.searchParams.set('direction', newDirection);
    } else {
        // Nuevo campo, comenzar con ascendente
        url.searchParams.set('order_by', field);
        url.searchParams.set('direction', 'asc');
    }
    
    // Resetear a página 1
    url.searchParams.delete('page');
    
    loadPeriodTable(url.toString());
}

// ===========================
// BÚSQUEDA EN TIEMPO REAL
// ===========================
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchInput');
    
    if (searchInput) {
        let searchTimeout;
        
        searchInput.addEventListener('input', function(e) {
            clearTimeout(searchTimeout);
            
            searchTimeout = setTimeout(() => {
                const searchValue = e.target.value.trim();
                const url = new URL(window.location.href);
                
                if (searchValue) {
                    url.searchParams.set('q', searchValue);
                } else {
                    url.searchParams.delete('q');
                }
                
                // Resetear a página 1 al buscar
                url.searchParams.delete('page');
                
                // Cargar tabla con búsqueda
                loadPeriodTable(url.toString());
            }, 500); // Esperar 500ms después de que el usuario deje de escribir
        });
    }
});

// ===========================
// CARGAR TABLA VÍA AJAX
// ===========================
function loadPeriodTable(url) {
    const tableContainer = document.getElementById('tableContainer');
    
    // Mostrar indicador de carga
    tableContainer.style.opacity = '0.5';
    
    fetch(url, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.text())
    .then(html => {
        // Extraer solo la tabla del HTML completo
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const newTable = doc.getElementById('tableContainer');
        
        if (newTable) {
            tableContainer.innerHTML = newTable.innerHTML;
        }
        
        tableContainer.style.opacity = '1';
        
        // Actualizar URL sin recargar página
        window.history.pushState({}, '', url);
        
        // Re-adjuntar eventos de paginación
        attachPaginationEvents();
    })
    .catch(error => {
        console.error('Error cargando tabla:', error);
        tableContainer.style.opacity = '1';
    });
}

// ===========================
// EVENTOS DE PAGINACIÓN
// ===========================
function attachPaginationEvents() {
    const paginationButtons = document.querySelectorAll('.pagination-container button.page-btn:not([disabled])');
    
    paginationButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            // El onclick ya está en el HTML, no necesitamos hacer nada más aquí
        });
    });
}

// Adjuntar eventos al cargar página
document.addEventListener('DOMContentLoaded', attachPaginationEvents);

// ===========================
// MODAL DE PERIODO
// ===========================
function open_modal(url) {
    const modalContainer = document.getElementById('popupPeriod');

    fetch(url)
        .then(response => {
            if (!response.ok) throw new Error('Error de red');
            return response.text();
        })
        .then(html => {
            modalContainer.innerHTML = html;
            modalContainer.classList.add('open');

            // --- CORRECCIÓN AQUÍ ---
            // Buscamos por CLASE, no por atributo data-dismiss
            const closeButtons = modalContainer.querySelectorAll('.js-close-modal');

            closeButtons.forEach(btn => {
                btn.onclick = function (e) {
                    e.preventDefault(); // Prevenir submit si es type="submit" por error
                    close_modal();
                };
            });

            // Cerrar al hacer click fuera del modal
            modalContainer.onclick = function (event) {
                // Verificamos que el click sea en el fondo oscuro y no dentro del contenido
                if (event.target === modalContainer) {
                    close_modal();
                }
            }
            
            // Adjuntar submit del formulario
            attachFormSubmit();
        })
        .catch(error => console.error('Error cargando modal:', error));
}

function close_modal() {
    const modalContainer = document.getElementById('popupPeriod');
    modalContainer.classList.remove('open');
    setTimeout(() => {
        modalContainer.innerHTML = '';
    }, 200); // Esperar pequeña transición si la tienes
}

// ===========================
// SUBMIT DEL FORMULARIO CON AJAX
// ===========================
function attachFormSubmit() {
    const form = document.getElementById('periodForm');
    if (!form) return;
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.innerHTML;
        
        // Deshabilitar botón y mostrar loading
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
                // Cerrar modal y recargar tabla
                close_modal();
                loadPeriodTable(window.location.href);
            } else {
                // Mostrar errores en el formulario
                if (data.errors) {
                    for (const [field, errors] of Object.entries(data.errors)) {
                        const errorDiv = document.getElementById(`error-${field}`);
                        const inputField = document.getElementById(`id_${field}`);
                        
                        if (errorDiv) {
                            errorDiv.innerHTML = `<small class="text-danger">${errors.join(', ')}</small>`;
                        }
                        if (inputField) {
                            inputField.classList.add('is-invalid');
                        }
                    }
                }
            }
        })
        .catch(error => {
            console.error('Error:', error);
        })
        .finally(() => {
            // Rehabilitar botón
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        });
    });
}