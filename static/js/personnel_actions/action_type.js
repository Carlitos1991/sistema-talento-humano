document.addEventListener('DOMContentLoaded', () => {

    let tableState = {status: '', q: '', page: 1, pageSize: 10};
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
                if (wrapper) wrapper.innerHTML = html;
            }
        } catch (error) {
            console.error("Error al cargar:", error);
        }
    }

    function initTableLogic() {
        window.debouncedSearch = () => {
            const input = document.getElementById('searchInput');
            if (input) {
                tableState.q = input.value;
                tableState.page = 1;
                loadTableData();
            }
        };
        window.changePage = (pageNumber) => {
            tableState.page = pageNumber;
            loadTableData();
        };
    }

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
                    id: null, // <--- VITAL PARA ACTUALIZAR
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

                    $selects.on('select2:open', function () {
                        $('#action-type-modal-app .modal-body-scrolled').css('overflow-y', 'hidden');

                        setTimeout(() => {
                            const searchInput = document.querySelector('.select2-container--open .select2-search__field');
                            if (searchInput) searchInput.focus();
                        }, 50);
                    });


                    $selects.on('select2:close', function () {
                        $('#action-type-modal-app .modal-body-scrolled').css('overflow-y', 'auto');
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
                    id: null, // Limpiamos ID
                    code: '', name: '', is_active: true,
                    default_authority_1: null, default_authority_2: null,
                    default_reviewer: null, default_register: null
                };
                this.isVisible = true;

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
                        id: data.id, // <--- AHORA SÍ RECOGE EL ID PARA EDITAR
                        code: data.code,
                        name: data.name,
                        is_active: data.is_active,
                        default_authority_1: data.auth1_id,
                        default_authority_2: data.auth2_id,
                        default_reviewer: data.reviewer_id,
                        default_register: data.register_id
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

                // Como ya tenemos this.formData.id, el servidor sabrá exactamente a quién actualizar
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
                        loadTableData();
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
    }

    window.openActionTypeModal = () => modalInstance && modalInstance.openForCreate();
    window.editActionType = (id) => modalInstance && modalInstance.openForEdit(id);

    window.deleteActionType = async (id) => {
        Swal.fire({title: '¿Eliminar?', icon: 'warning', showCancelButton: true, confirmButtonText: 'Sí'})
            .then(async (result) => {
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