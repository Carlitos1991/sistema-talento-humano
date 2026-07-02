// 1. Estado global (Fuera del DOMContentLoaded para evitar problemas de scope)
let tableState = {status: '', q: '', page: 1, pageSize: 10};
let modalInstance = null;

// ==========================================
// 2. LÓGICA DE TABLA (Paginación, Búsqueda, Eliminación)
// Definida globalmente para que el HTML siempre las encuentre
// ==========================================
window.loadTableData = async () => {
    const params = new URLSearchParams();
    if (tableState.status) params.append('status', tableState.status);
    if (tableState.q) params.append('q', tableState.q);
    if (tableState.page) params.append('page', tableState.page);

    const url = `${window.location.pathname}?${params.toString()}`;
    try {
        const response = await fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}});
        if (response.ok) {
            const html = await response.text();
            const wrapper = document.getElementById('table-content-wrapper');
            if (wrapper) wrapper.innerHTML = html;
        } else {
            console.error("El servidor devolvió un error:", response.status);
        }
    } catch (error) {
        console.error("Error crítico al cargar los datos de la tabla:", error);
    }
};

window.debouncedSearch = () => {
    const input = document.getElementById('searchInput');
    if (input) {
        tableState.q = input.value;
        tableState.page = 1; // Volver a la página 1 al buscar
        window.loadTableData();
    }
};

window.changePage = (pageNumber) => {
    tableState.page = pageNumber;
    window.loadTableData();
};

window.deleteActionType = async (id) => {
    if (typeof Swal === 'undefined') {
        alert("Error: SweetAlert2 no está cargado en la página.");
        return;
    }

    Swal.fire({title: '¿Eliminar?', icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí'})
        .then(async (result) => {
            if (result.isConfirmed) {
                try {
                    const response = await fetch(`/personnel_actions/types/api/delete/${id}/`, {
                        method: 'POST',
                        headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}
                    });
                    const res = await response.json();
                    if (res.success) {
                        Swal.fire('Eliminado', '', 'success');
                        window.loadTableData();
                    }
                } catch (error) {
                    Swal.fire('Error', 'Fallo al intentar eliminar.', 'error');
                }
            }
        });
};

// ==========================================
// 3. LÓGICA DE VUE (Modal de Creación/Edición)
// ==========================================
window.openActionTypeModal = () => {
    if (modalInstance) modalInstance.openForCreate();
    else console.error("Error: El modal no se inicializó correctamente.");
};

window.editActionType = (id) => {
    if (modalInstance) modalInstance.openForEdit(id);
    else console.error("Error: El modal no se inicializó correctamente.");
};

document.addEventListener('DOMContentLoaded', () => {
    try {
        // Validación de dependencias para no romper la ejecución
        if (typeof Vue === 'undefined' || !Vue.createApp) {
            console.error("Vue 3 no está definido. Revisa que el CDN de Vue esté cargado en tu base.html.");
            return;
        }

        const {createApp} = Vue;

        const actionTypeModalApp = createApp({
            delimiters: ['[[', ']]'],
            data() {
                return {
                    isVisible: false,
                    isEdit: false,
                    loading: false,
                    errors: {},
                    formData: {
                        id: null,
                        code: '',
                        name: '',
                        is_active: true,
                        default_authority_1: null,
                        default_authority_2: null,
                        default_reviewer: null,
                        default_register: null
                    }
                };
            },
            methods: {
                closeModal() {
                    this.isVisible = false;
                },

                initSelect2AJAX() {
                    this.$nextTick(() => {
                        const self = this;
                        // Si jQuery no está cargado, evitamos que crashee
                        if (typeof $ === 'undefined') return;

                        const $selects = $('.action-type-user-select');
                        if ($selects.hasClass('select2-hidden-accessible')) {
                            $selects.select2('destroy').off('change');
                        }

                        $selects.each(function () {
                            $(this).select2({
                                width: '100%',
                                dropdownParent: $('#action-type-modal-app .modal-container'),
                                placeholder: 'Escriba para buscar...',
                                allowClear: true,
                                minimumInputLength: 3,
                                ajax: {
                                    url: '/personnel_actions/api/users/search/',
                                    dataType: 'json',
                                    delay: 250,
                                    data: function (params) {
                                        return {
                                            q: params.term || '',
                                            term: params.term || '',
                                            search: params.term || ''
                                        };
                                    },
                                    processResults: function (data) {
                                        return {results: data.results || data};
                                    }
                                }
                            }).on('change', function () {
                                const elementId = $(this).attr('id');
                                const modelKey = elementId.replace('id_', '');
                                self.formData[modelKey] = $(this).val();
                            });
                        });
                    });
                },

                setSelect2Value(elementId, id, text) {
                    if (typeof $ === 'undefined') return;
                    let element = $('#' + elementId);
                    if (id && text) {
                        if (element.find("option[value='" + id + "']").length === 0) {
                            let newOption = new Option(text, id, true, true);
                            element.append(newOption);
                        }
                        element.val(id).trigger('change.select2');
                    } else {
                        element.val(null).trigger('change.select2');
                    }
                },

                openForCreate() {
                    this.isEdit = false;
                    this.errors = {};
                    this.formData = {
                        id: null, code: '', name: '', is_active: true,
                        default_authority_1: null, default_authority_2: null,
                        default_reviewer: null, default_register: null
                    };
                    this.isVisible = true;
                    this.initSelect2AJAX();
                    ['1', '2', 'reviewer', 'register'].forEach(x => this.setSelect2Value(`id_default_${x.includes('r') ? x : 'authority_' + x}`, null, ''));
                },

                async openForEdit(id) {
                    this.isEdit = true;
                    this.errors = {};
                    this.isVisible = true;

                    try {
                        const response = await fetch(`/personnel_actions/types/api/detail/${id}/`);
                        const data = await response.json();

                        this.formData = {
                            id: data.id, code: data.code, name: data.name, is_active: data.is_active,
                            default_authority_1: data.auth1_id, default_authority_2: data.auth2_id,
                            default_reviewer: data.reviewer_id, default_register: data.register_id
                        };

                        this.initSelect2AJAX();
                        this.setSelect2Value('id_default_authority_1', data.auth1_id, data.auth1_text);
                        this.setSelect2Value('id_default_authority_2', data.auth2_id, data.auth2_text);
                        this.setSelect2Value('id_default_reviewer', data.reviewer_id, data.reviewer_text);
                        this.setSelect2Value('id_default_register', data.register_id, data.register_text);
                    } catch (error) {
                        Swal.fire('Error', 'No se pudieron cargar los datos', 'error');
                    }
                },

                async saveData() {
                    this.loading = true;
                    this.errors = {};
                    const url = this.isEdit ? `/personnel_actions/types/api/save/${this.formData.id}/` : '/personnel_actions/types/api/save/';

                    try {
                        const response = await fetch(url, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': getCookie('csrftoken'),
                                'X-Requested-With': 'XMLHttpRequest'
                            },
                            body: JSON.stringify(this.formData)
                        });

                        const res = await response.json();
                        if (res.success) {
                            Swal.fire({
                                icon: 'success',
                                title: 'Guardado con éxito',
                                timer: 1500,
                                showConfirmButton: false
                            });
                            this.closeModal();
                            window.loadTableData(); // Llama a la función global ahora
                        } else {
                            this.errors = res.errors || {};
                        }
                    } catch (error) {
                        Swal.fire('Error', 'Fallo al guardar la petición.', 'error');
                    } finally {
                        this.loading = false;
                    }
                }
            }
        });

        const modalTarget = document.getElementById('action-type-modal-app');
        if (modalTarget) {
            modalInstance = actionTypeModalApp.mount('#action-type-modal-app');
        } else {
            console.warn("Advertencia: No se encontró el elemento con id 'action-type-modal-app' en el DOM.");
        }
    } catch (error) {
        console.error("Error al inicializar la aplicación Vue:", error);
    }
});

// ==========================================
// 4. UTILIDADES
// ==========================================
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}