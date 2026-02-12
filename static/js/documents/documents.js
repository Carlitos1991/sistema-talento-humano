// documents.js

document.addEventListener('DOMContentLoaded', function() {
    // Inicializar Select2 dentro del modal si es necesario
    $('.select2-modal').select2({
        dropdownParent: $('#documentModal')
    });
});

let searchTimeout;

function filterDocuments() {
    const query = document.getElementById('searchInput').value;
    clearTimeout(searchTimeout);

    searchTimeout = setTimeout(() => {
        const url = `${window.location.pathname}?q=${encodeURIComponent(query)}`;

        fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.json())
        .then(data => {
            document.getElementById('tableContainer').innerHTML = data.html;
        })
        .catch(error => console.error('Error:', error));
    }, 300); // Debounce de 300ms
}

function openDocumentModal() {
    const modalEl = document.getElementById('documentModal');
    const modal = new bootstrap.Modal(modalEl);
    document.getElementById('documentForm').reset();
    document.getElementById('modalTitle').innerText = 'Nuevo Documento';
    modal.show();
}

function saveDocument() {
    const form = document.getElementById('documentForm');
    const formData = new FormData(form);

    // Aquí iría la lógica fetch POST a la URL de crear
    // Usar SweetAlert2 para feedback
}