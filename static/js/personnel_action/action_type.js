/* static/js/personnel_action/action_type.js */

document.addEventListener('DOMContentLoaded', () => {

    // =========================================================
    // 1. LÓGICA DE TABLA (FILTROS Y PAGINACIÓN LOCAL)
    // =========================================================
    let tableState = {
        status: '',
        q: '',
        page: 1,
        pageSize: 10
    };

    let allRows = [];
    let filteredRows = [];

    initTableLogic();

    async function loadTableData() {
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
                if (wrapper) {
                    wrapper.innerHTML = html;
                }
            }
        } catch (error) {
            console.error("Error al cargar la tabla:", error);
        }
    }

    function initTableLogic() {
        window.debouncedSearch = () => {
            const input = document.getElementById('searchInput');
            if (input) {
                tableState.q = input.value;
                tableState.page = 1; // Al buscar texto, siempre volvemos a la página 1
                loadTableData();
            }
        };
        window.changePage = (pageNumber) => {
            tableState.page = pageNumber;
            loadTableData();
        };
    }

    // =========================================================
    // 2. LOGICA DEL MODAL (VUE.JS + SELECT2 AJAX)
    // =========================================================

    // Variable global local al DOMContentLoaded para guardar la instancia montada de Vue
    let modalInstance = null;

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
                    const $selects = $('.action-type-user-select');
                    if ($selects.hasClass('select2-hidden-accessible')) {
                        $selects.select2('destroy').off('change');
                    }
                    // Limpiar inicializaciones anteriores por seguridad
                    $('.action-type-user-select').select2('destroy').off('change');

                    // Configurar el Select2 con tu API de búsqueda existente
                    $('.action-type-user-select').select2({
                        width: '100%',
                        dropdownParent: $('#action-type-modal-app'), // Clave para renderizar dentro de Vue
                        placeholder: 'Empiece a escribir para buscar... (Mín. 3 letras)',
                        allowClear: true,
                        minimumInputLength: 3,
                        ajax: {
                            url: '/personnel_actions/api/users/search/', // Tu URL oficial configurada
                            dataType: 'json',
                            delay: 250,
                            data: function (params) {
                                return {q: params.term};
                            },
                            processResults: function (data) {
                                // Mapea los resultados retornados por user_search_json
                                return {results: data.results || data};
                            }
                        }
                    }).on('change', function () {
                        // Capturar el ID del elemento modificado por jQuery y enviarlo a Vue
                        const elementId = $(this).attr('id');
                        const modelKey = elementId.replace('id_', ''); // default_authority_1
                        self.formData[modelKey] = $(this).val();
                    });
                });
            },

            setSelect2Value(elementId, id, text) {
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
                    code: '', name: '', is_active: true,
                    default_authority_1: null, default_authority_2: null,
                    default_reviewer: null, default_register: null
                };
                this.isVisible = true;

                // Inicializar controles vacíos
                this.initSelect2AJAX();
                this.setSelect2Value('id_default_authority_1', null, '');
                this.setSelect2Value('id_default_authority_2', null, '');
                this.setSelect2Value('id_default_reviewer', null, '');
                this.setSelect2Value('id_default_register', null, '');
            },

            async openForEdit(id) {
                this.isEdit = true;
                this.errors = {};
                this.isVisible = true;

                try {
                    const response = await fetch(`/personnel_actions/types/api/detail/${id}/`);
                    const data = await response.json();

                    this.formData = {
                        code: data.code,
                        name: data.name,
                        is_active: data.is_active,
                        default_authority_1: data.auth1_id,
                        default_authority_2: data.auth2_id,
                        default_reviewer: data.reviewer_id,
                        default_register: data.register_id
                    };

                    // Inicializar e inyectar valores guardados
                    this.initSelect2AJAX();
                    this.setSelect2Value('id_default_authority_1', data.auth1_id, data.auth1_text);
                    this.setSelect2Value('id_default_authority_2', data.auth2_id, data.auth2_text);
                    this.setSelect2Value('id_default_reviewer', data.reviewer_id, data.reviewer_text);
                    this.setSelect2Value('id_default_register', data.register_id, data.register_text);

                } catch (error) {
                    console.error("Error al cargar detalles de tipo:", error);
                    Swal.fire('Error', 'No se pudieron cargar los datos del registro', 'error');
                }
            },

            async saveData() {
                this.loading = true;
                this.errors = {};

                // Determinar si es alta o modificación
                const url = this.isEdit
                    ? `/personnel_actions/types/api/save/${this.formData.id}/`
                    : '/personnel_actions/types/api/save/';

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
                        loadTableData(); // Recargar la lista visual
                    } else {
                        this.errors = res.errors || {};
                    }
                } catch (error) {
                    Swal.fire('Error', 'Sucedió un fallo inesperado al guardar', 'error');
                } finally {
                    this.loading = false;
                }
            }
        }
    });

    // Validar existencia del contenedor HTML para evitar fallos de Vue
    const modalTarget = document.getElementById('action-type-modal-app');
    if (modalTarget) {
        // ASIGNACIÓN CRUCIAL: Aquí guardamos la instancia de la aplicación montada
        modalInstance = actionTypeModalApp.mount('#action-type-modal-app');
    } else {
        console.error("No se encontró el contenedor id='action-type-modal-app' en el modal HTML.");
    }

    // =========================================================
    // 3. PUENTES GLOBALES PARA ONCLICK INLINE (HTML)
    // =========================================================
    window.openActionTypeModal = () => {
        if (modalInstance) {
            modalInstance.openForCreate();
        } else {
            console.error("Vue no se ha inicializado correctamente.");
        }
    };

    window.editActionType = (id) => {
        if (modalInstance) {
            modalInstance.openForEdit(id);
        }
    };

    window.deleteActionType = async (id) => {
        Swal.fire({
            title: '¿Eliminar?', icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí'
        }).then(async (result) => {
            if (result.isConfirmed) {
                const response = await fetch(`/personnel_actions/types/api/delete/${id}/`, {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('csrftoken'), 'X-Requested-With': 'XMLHttpRequest'}
                });
                const res = await response.json();
                if (res.success) {
                    Swal.fire('Eliminado', '', 'success');
                    loadTableData();
                }
            }
        });
    };
});

// Helper CSRF Cookie
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