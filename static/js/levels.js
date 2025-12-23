/* static/js/levels.js */

document.addEventListener('DOMContentLoaded', () => {
    const {createApp, ref} = Vue;
    const tableContainer = document.getElementById('table-content-wrapper');
    const searchInput = document.getElementById('table-search');
    let currentFilters = {q: '', status: 'all', page: 1};

    // Configuración Global del Toast (Esquina superior derecha)
    const Toast = Swal.mixin({
        toast: true,
        position: 'top-end',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
            toast.addEventListener('mouseenter', Swal.stopTimer)
            toast.addEventListener('mouseleave', Swal.resumeTimer)
        }
    });

    // --- 1. LÓGICA DE TABLA ---
    window.fetchLevels = function (params = {}) {
        if (params.reset) currentFilters = {q: '', status: 'all', page: 1};
        else Object.assign(currentFilters, params);

        const url = new URL(window.location.href);
        Object.keys(currentFilters).forEach(key => {
            if (currentFilters[key]) url.searchParams.set(key, currentFilters[key]);
        });

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                if (tableContainer) {
                    tableContainer.innerHTML = html;
                    updatePaginationUI();
                }
            })
            .catch(err => console.error("Error:", err));
    };

    function updatePaginationUI() {
        const meta = document.getElementById('pagination-metadata');
        if (!meta) return;
        const total = meta.dataset.total;
        const start = meta.dataset.start;
        const end = meta.dataset.end;
        const page = parseInt(meta.dataset.page);

        const infoEl = document.getElementById('page-info');
        if (infoEl) infoEl.textContent = total == 0 ? "Sin resultados" : `Mostrando ${start}-${end} de ${total}`;

        const displayEl = document.getElementById('current-page-display');
        if (displayEl) displayEl.textContent = page;

        const prevBtn = document.getElementById('btn-prev');
        const nextBtn = document.getElementById('btn-next');
        if (prevBtn) prevBtn.disabled = meta.dataset.hasPrev !== 'true';
        if (nextBtn) nextBtn.disabled = meta.dataset.hasNext !== 'true';
    }

    if (searchInput) {
        let timeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => window.fetchLevels({q: e.target.value, page: 1}), 500);
        });
    }

    window.filterByStatus = function (status) {
        document.querySelectorAll('.stat-card').forEach(c => c.classList.add('opacity-low'));
        const activeCard = document.getElementById(status === 'all' ? 'card-filter-all' : (status === 'true' ? 'card-filter-active' : 'card-filter-inactive'));
        if (activeCard) activeCard.classList.remove('opacity-low');
        window.fetchLevels({status: status, page: 1});
    };

    // --- 2. MODAL VUE ---
    if (document.getElementById('level-modal-app')) {
        createApp({
            delimiters: ['[[', ']]'],
            setup() {
                const isVisible = ref(false);
                const isEditing = ref(false);
                const currentId = ref(null);
                const errors = ref({});
                const formEl = 'levelForm';

                const openCreate = () => {
                    isEditing.value = false;
                    currentId.value = null;
                    errors.value = {};
                    document.getElementById(formEl).reset();
                    isVisible.value = true;
                    document.body.classList.add('no-scroll');
                };

                const openEdit = async (id) => {
                    isEditing.value = true;
                    currentId.value = id;
                    errors.value = {};
                    try {
                        const res = await fetch(`/institution/levels/detail/${id}/`);
                        const data = await res.json();
                        if (data.success) {
                            const d = data.data;
                            const form = document.getElementById(formEl);
                            form.querySelector('[name=name]').value = d.name;
                            // El campo level_order ya no existe en el form, no hace falta setearlo
                            isVisible.value = true;
                            document.body.classList.add('no-scroll');
                        }
                    } catch (e) {
                        Toast.fire({icon: 'error', title: 'Error al cargar datos'});
                    }
                };

                const closeModal = () => {
                    isVisible.value = false;
                    document.body.classList.remove('no-scroll');
                };

                const submitForm = async () => {
                    const formData = new FormData(document.getElementById(formEl));
                    const url = isEditing.value
                        ? `/institution/levels/update/${currentId.value}/`
                        : `/institution/levels/create/`;

                    try {
                        const res = await fetch(url, {
                            method: 'POST', body: formData,
                            headers: {'X-Requested-With': 'XMLHttpRequest'}
                        });
                        const data = await res.json();

                        if (data.success) {
                            Toast.fire({icon: 'success', title: data.message});
                            closeModal();
                            window.fetchLevels();
                            if (data.new_stats) updateStats(data.new_stats);
                        } else {
                            errors.value = data.errors;
                        }
                    } catch (e) {
                        Toast.fire({icon: 'error', title: 'Error del servidor'});
                    }
                };

                window.openEditLevel = openEdit;
                // Exponer al scope para el botón "Nuevo"
                window.openCreateLevel = openCreate;

                return {isVisible, isEditing, errors, closeModal, submitForm};
            }
        }).mount('#level-modal-app');

        // Listener botón nuevo
        const btnNew = document.getElementById('btn-add-level');
        if (btnNew) btnNew.onclick = () => window.openCreateLevel();
    }

    // --- 3. TOGGLE STATUS (CORREGIDO) ---
    window.toggleLevelStatus = async (btnElement, url, name) => {
        // Detectar estado actual visualmente
        const isCurrentlyActive = btnElement.classList.contains('btn-delete-action');
        const actionVerb = isCurrentlyActive ? 'Desactivar' : 'Activar';
        const btnClass = isCurrentlyActive ? 'btn-swal-danger' : 'btn-swal-success';

        const result = await Swal.fire({
            title: `¿${actionVerb} nivel?`,
            text: `Vas a cambiar el estado de "${name}"`,
            icon: 'warning',
            showCancelButton: true,

            buttonsStyling: false,
            customClass: {
                confirmButton: `swal2-confirm ${btnClass}`,
                cancelButton: 'swal2-cancel btn-swal-cancel',
                popup: 'swal2-popup'
            },
            confirmButtonText: `Sí, ${actionVerb.toLowerCase()}`,
            cancelButtonText: 'Cancelar'
        });

        if (result.isConfirmed) {
            try {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

                const res = await fetch(url, {
                    method: 'POST',
                    body: formData,
                    headers: {'X-Requested-With': 'XMLHttpRequest'}
                });
                const data = await res.json();

                if (data.success) {
                    // Toast de Éxito
                    Toast.fire({icon: 'success', title: data.message});

                    if (data.new_stats) updateStats(data.new_stats);

                    // Recargar tabla para actualizar iconos/colores
                    window.fetchLevels();
                } else {
                    // Toast de Error (ej: Conflicto de nivel activo)
                    Toast.fire({icon: 'error', title: data.message});
                }
            } catch (e) {
                console.error(e);
                Toast.fire({icon: 'error', title: 'Error de conexión'});
            }
        }
    };

    function updateStats(stats) {
        const t = document.getElementById('stat-total');
        const a = document.getElementById('stat-active');
        const i = document.getElementById('stat-inactive');
        if (t) t.textContent = stats.total;
        if (a) a.textContent = stats.active;
        if (i) i.textContent = stats.inactive;
    }

    // Listeners Paginación
    const pPrev = document.getElementById('btn-prev');
    const pNext = document.getElementById('btn-next');
    if (pPrev) pPrev.onclick = () => window.fetchLevels({page: currentFilters.page - 1});
    if (pNext) pNext.onclick = () => window.fetchLevels({page: currentFilters.page + 1});

    // Inicializar
    updatePaginationUI();
});