/* static/js/apps/person.js */

let vueApp = null;

// --- FUNCIONES GLOBALES (Accesibles desde HTML) ---
window.toggleSearchModal = (show) => {
    const el = document.getElementById('modalAdvancedSearch');
    if (el) {
        show ? el.classList.remove('hidden') : el.classList.add('hidden');
        document.body.classList.toggle('no-scroll', show);
    } else {
        console.warn('El modal modalAdvancedSearch no existe en el DOM.');
    }
};

window.applyAdvancedSearch = () => {
    if (vueApp) vueApp.handleAdvancedSearch();
    window.toggleSearchModal(false);
};

window.resetAdvancedSearch = () => {
    document.getElementById('advancedSearchForm')?.reset();
    $('.select2-field').val(null).trigger('change');
    if (vueApp) vueApp.resetFilters();
};

window.changePage = (page) => {
    if (vueApp) vueApp.fetchPeople(page);
};

window.quickFilterStatus = (statusId) => {
    const statusSelect = document.querySelector('select[name="status"]');
    if (statusSelect) {
        statusSelect.value = statusId;
        $(statusSelect).trigger('change');
    }
    if (vueApp) vueApp.applyQuickFilter(statusId);
};


document.addEventListener('DOMContentLoaded', () => {
    const appElement = document.getElementById('personApp');
    if (!appElement) return;

    const {createApp, ref, onMounted, nextTick} = Vue;
    let urls = {};
    try {
        urls = JSON.parse(appElement.dataset.urls);
    } catch (e) {
        console.error(e);
    }

    const app = createApp({
        setup() {
            // --- 1. DEFINICIÓN DE VARIABLES REACTIVAS ---

            // Filtros y Búsqueda
            const activeFilters = ref({});

            // Vista Rápida
            const loadingQuickView = ref(false);
            const quickViewHtml = ref('');
            const currentDetailUrl = ref('#');

            // Formularios (Crear/Editar)
            const isEditing = ref(false);
            const form = ref({});
            const errors = ref({});
            const photoPreview = ref(null);
            const currentId = ref(null);

            // Credenciales
            const credsForm = ref({username: '', password: '', role: ''});
            const credsErrors = ref({});

            // ----------------------------------------------------
            // 2. BÚSQUEDA INMEDIATA (FRONTEND)
            // ----------------------------------------------------
            const initLocalSearch = () => {
                const input = document.getElementById('searchInput');
                if (!input) return;

                // Clonamos para limpiar eventos previos
                const newInput = input.cloneNode(true);
                input.parentNode.replaceChild(newInput, input);

                newInput.addEventListener('input', (e) => {
                    const term = e.target.value.toLowerCase().trim();
                    const rows = document.querySelectorAll('#table-body tr.location-row');
                    let visibleCount = 0;

                    rows.forEach(row => {
                        const text = row.innerText.toLowerCase();
                        if (text.includes(term) || term === '') {
                            row.style.display = '';
                            visibleCount++;
                        } else {
                            row.style.display = 'none';
                        }
                    });

                    const noResultsRow = document.getElementById('client-no-results');
                    if (noResultsRow) {
                        if (visibleCount === 0 && rows.length > 0) {
                            noResultsRow.style.display = '';
                        } else {
                            noResultsRow.style.display = 'none';
                        }
                    }
                });
            };

            // ----------------------------------------------------
            // 3. BÚSQUEDA AVANZADA & PAGINACIÓN (BACKEND)
            // ----------------------------------------------------
            const fetchPeople = async (page = 1) => {
                const params = new URLSearchParams();
                params.append('page', page);

                for (const [key, value] of Object.entries(activeFilters.value)) {
                    if (value) params.append(key, value);
                }

                try {
                    const response = await fetch(`${urls.list}?${params.toString()}`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const data = await response.json();

                    if (data.success) {
                        const container = document.getElementById('tableContainer');
                        if (container) {
                            container.innerHTML = data.html;
                            const searchInput = document.getElementById('searchInput');
                            if (searchInput) searchInput.value = '';
                        }
                    }
                } catch (error) {
                    console.error("Error fetching data:", error);
                }
            };

            const handleAdvancedSearch = () => {
                const formData = new FormData(document.getElementById('advancedSearchForm'));
                activeFilters.value = Object.fromEntries(formData.entries());
                fetchPeople(1);
            };

            const resetFilters = () => {
                activeFilters.value = {};
                fetchPeople(1);
            };

            const applyQuickFilter = (statusId) => {
                activeFilters.value = {'status': statusId};
                fetchPeople(1);
            };

            // ----------------------------------------------------
            // 4. VISTA RÁPIDA (DELEGACIÓN DE EVENTOS)
            // ----------------------------------------------------
            const initTableListeners = () => {
                const container = document.getElementById('tableContainer');
                if (!container) return;

                container.addEventListener('click', (e) => {
                    const btn = e.target.closest('.btn-quick-view');
                    if (btn) {
                        e.preventDefault();
                        const personId = btn.dataset.id;
                        if (personId) {
                            openQuickView(personId);
                        }
                    }
                });
            };

            const openQuickView = async (id) => {
                loadingQuickView.value = true;
                quickViewHtml.value = '<div class="p-4 text-center text-gray-500">Cargando información...</div>';
                currentDetailUrl.value = `/employee/detail/${id}/`;

                const modal = document.getElementById('modalQuickViewOverlay');
                showModal(modal);

                try {
                    const res = await fetch(`/person/quick-view-partial/${id}/`);
                    if (res.ok) {
                        quickViewHtml.value = await res.text();
                    } else {
                        quickViewHtml.value = '<p class="text-error p-4">No se pudo cargar la información.</p>';
                    }
                } catch (e) {
                    quickViewHtml.value = '<p class="text-error p-4">Error de conexión.</p>';
                } finally {
                    loadingQuickView.value = false;
                }
            };

            const closeQuickView = () => {
                hideModal(document.getElementById('modalQuickViewOverlay'));
            };

            // ----------------------------------------------------
            // 5. MODALES Y FORMULARIOS
            // ----------------------------------------------------
            const showModal = (el) => {
                if (el) {
                    el.classList.remove('hidden');
                    document.body.classList.add('no-scroll');
                }
            };
            const hideModal = (el) => {
                if (el) {
                    el.classList.add('hidden');
                    if (document.querySelectorAll('.modal-overlay:not(.hidden)').length === 0) {
                        document.body.classList.remove('no-scroll');
                    }
                }
            };

            const submitPersonForm = async () => {
                errors.value = {};
                const formData = new FormData(document.getElementById('personFormHtml'));
                const url = isEditing.value ? urls.update.replace('0', currentId.value) : urls.create;

                try {
                    const res = await fetch(url, {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                    });
                    const data = await res.json();

                    if (data.success) {
                        if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                        hideModal(document.getElementById('modalPersonOverlay'));
                        fetchPeople(1);
                    } else {
                        errors.value = data.errors;
                        if (window.Toast) window.Toast.fire({icon: 'warning', title: 'Revise el formulario'});
                    }
                } catch (e) {
                    console.error(e);
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error servidor'});
                }
            };

            // Credenciales
            const openCredsModal = (id) => {
                currentId.value = id;
                credsForm.value = {username: '', password: '', role: ''};
                credsErrors.value = {};
                showModal(document.getElementById('modalCredentialsOverlay'));
            };

            const submitCredsForm = async () => {
                credsErrors.value = {};
                const formData = new FormData();
                formData.append('username', credsForm.value.username);
                formData.append('password', credsForm.value.password);
                formData.append('role', credsForm.value.role);

                try {
                    const res = await fetch(urls.createCredentials.replace('0', currentId.value), {
                        method: 'POST',
                        body: formData,
                        headers: {'X-CSRFToken': window.getCookie('csrftoken')}
                    });
                    const data = await res.json();

                    if (data.success) {
                        if (window.Toast) window.Toast.fire({icon: 'success', title: data.message});
                        hideModal(document.getElementById('modalCredentialsOverlay'));
                        fetchPeople(1);
                    } else {
                        credsErrors.value = data.errors;
                    }
                } catch (e) {
                    if (window.Toast) window.Toast.fire({icon: 'error', title: 'Error creando credenciales'});
                }
            };

            const closeModal = () => {
                hideModal(document.getElementById('modalPersonOverlay'));
                hideModal(document.getElementById('modalCredentialsOverlay'));
            };

            // ----------------------------------------------------
            // 6. MANEJO DE SELECT2 Y CASCADA (CORREGIDO)
            // ----------------------------------------------------
            const initModalSelect2 = () => {
                const $selects = $('#modalPersonOverlay select.select2-field');

                // 1. Destruir instancias previas
                $selects.each(function () {
                    if ($(this).hasClass("select2-hidden-accessible")) {
                        $(this).select2('destroy');
                    }
                });

                // 2. Inicializar Select2
                $selects.select2({
                    dropdownParent: $('#modalPersonOverlay'),
                    width: '100%',
                    placeholder: "-- Seleccione --",
                    allowClear: true
                }).on('change', function () {
                    // A. Sincronizar con Vue
                    const fieldName = $(this).attr('name');
                    const newVal = $(this).val();

                    if (form.value && fieldName) {
                        form.value[fieldName] = newVal;
                    }

                    // B. Manejo de Cascada (DIRECTO, SIN DISPATCHEVENT)
                    // Esto evita el bucle infinito "RangeError"
                    const map = {
                        'id_country': 'id_province',
                        'id_province': 'id_canton',
                        'id_canton': 'id_parish'
                    };

                    // Si el select que cambió está en el mapa, cargar hijos
                    if (map[this.id]) {
                        loadLocationChildren(newVal, map[this.id]);
                    }
                });
            };

            // Función auxiliar cascada (Llamada directamente, no por evento)
            const loadLocationChildren = async (parentId, targetSelectId, selectedValue = null) => {
                const target = document.getElementById(targetSelectId);
                if (!target) return;

                // Limpiar visualmente mientras carga
                target.innerHTML = '<option value="">Cargando...</option>';
                if ($(target).hasClass("select2-hidden-accessible")) {
                    $(target).trigger('change.select2'); // Actualizar visual Select2
                }

                if (!parentId) {
                    target.innerHTML = '<option value="">-- Seleccione --</option>';
                    if ($(target).hasClass("select2-hidden-accessible")) $(target).trigger('change.select2');
                    return;
                }

                try {
                    const response = await fetch(`${urls.locations}?parent_id=${parentId}&format=json`, {
                        headers: {'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const data = await response.json();

                    let options = '<option value="">-- Seleccione --</option>';
                    (Array.isArray(data) ? data : data.data || []).forEach(item => {
                        const isSelected = selectedValue == item.id ? 'selected' : '';
                        options += `<option value="${item.id}" ${isSelected}>${item.name}</option>`;
                    });

                    target.innerHTML = options;

                    // Notificar a Select2 que las opciones cambiaron
                    if ($(target).hasClass("select2-hidden-accessible")) {
                        $(target).trigger('change.select2');
                    }

                } catch (error) {
                    console.error("Error ubicaciones:", error);
                    target.innerHTML = '<option value="">Error</option>';
                }
            };

            // ----------------------------------------------------
            // 7. FUNCIONES DEL MODAL (CREAR/EDITAR)
            // ----------------------------------------------------

            const openCreateModal = async () => {
                isEditing.value = false;
                currentId.value = null;
                form.value = {
                    has_disability: false,
                    has_catastrophic_illness: false,
                    is_substitute: false
                };
                errors.value = {};
                photoPreview.value = null;

                const formEl = document.getElementById('personFormHtml');
                if (formEl) formEl.reset();

                showModal(document.getElementById('modalPersonOverlay'));

                await nextTick();

                // Limpiar selects dependientes
                $('#id_province').empty().append('<option value="">-- Seleccione --</option>');
                $('#id_canton').empty().append('<option value="">-- Seleccione --</option>');
                $('#id_parish').empty().append('<option value="">-- Seleccione --</option>');

                initModalSelect2();
            };

            const openEditModal = async (id) => {
                isEditing.value = true;
                currentId.value = id;
                errors.value = {};

                try {
                    const res = await fetch(urls.detail.replace('0', id));
                    const json = await res.json();

                    if (json.success) {
                        form.value = json.data;
                        photoPreview.value = json.data.photo_url;

                        showModal(document.getElementById('modalPersonOverlay'));

                        await nextTick();

                        // 1. Cargar Ubicaciones en Cascada (Secuencialmente)
                        if (json.data.country) {
                            await loadLocationChildren(json.data.country, 'id_province', json.data.province);
                        }
                        if (json.data.province) {
                            await loadLocationChildren(json.data.province, 'id_canton', json.data.canton);
                        }
                        if (json.data.canton) {
                            await loadLocationChildren(json.data.canton, 'id_parish', json.data.parish);
                        }

                        // 2. Iniciar Select2
                        initModalSelect2();

                        // 3. Forzar valores visuales
                        for (const [key, value] of Object.entries(json.data)) {
                            const el = $(`[name="${key}"]`);
                            if (el.length && el.hasClass('select2-field')) {
                                el.val(value).trigger('change.select2');
                            }
                        }
                    }
                } catch (e) {
                    console.error(e);
                }
            };

            // ----------------------------------------------------
            // CICLO DE VIDA
            // ----------------------------------------------------
            onMounted(() => {
                initLocalSearch();
                initTableListeners();

                // Select2 para el modal de búsqueda avanzada (independiente)
                $('.select2-field', '#modalAdvancedSearch').select2({
                    dropdownParent: $('#modalAdvancedSearch')
                });
            });

            return {
                // Métodos
                fetchPeople, handleAdvancedSearch, resetFilters, applyQuickFilter,
                openCreateModal, openEditModal, submitPersonForm,
                openCredsModal, submitCredsForm, closeModal,
                openQuickView, closeQuickView,

                // Estado Reactivo
                activeFilters,
                loadingQuickView, quickViewHtml, currentDetailUrl,
                isEditing, form, errors, photoPreview,
                credsForm, credsErrors
            };
        }
    });

    vueApp = app.mount('#personApp');
});