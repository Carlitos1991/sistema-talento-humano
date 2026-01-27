/* static/js/institution_deliverables.js */
const {createApp, ref, onMounted} = Vue;

createApp({
    delimiters: ['[[', ']]'],
    setup() {
        const container = document.getElementById('deliverables-app');
        const unitId = container.dataset.unitId;
        const csrfToken = container.dataset.csrf;

        const deliverables = ref([]);
        const showModal = ref(false); // DEBE empezar en false
        const editingId = ref(null);
        const form = ref({name: '', description: '', frequency: ''});

        const fetchDeliverables = async () => {
            try {
                const res = await fetch(`/institution/api/units/${unitId}/deliverables/`);
                const json = await res.json();
                if (json.success) {
                    deliverables.value = json.data;
                }
            } catch (error) {
                console.error("Error al obtener entregables:", error);
            }
        };

        // Función para limpiar el formulario
        const resetForm = () => {
            form.value = {name: '', description: '', frequency: ''};
            editingId.value = null;
        };

        const openModal = (item = null) => {
            if (item) {
                editingId.value = item.id;
                form.value = {
                    name: item.name,
                    description: item.description,
                    frequency: item.frequency
                };
            } else {
                resetForm();
            }
            showModal.value = true;
            document.body.style.overflow = 'hidden';
        };

        const closeModal = () => {
            showModal.value = false;
            resetForm();
            document.body.style.overflow = 'auto';
        };

        const saveDeliverable = async () => {
            if (!form.value.name.trim()) {
                Swal.fire({icon: 'warning', title: 'Atención', text: 'El nombre es obligatorio.'});
                return;
            }

            const formData = new FormData();
            formData.append('name', form.value.name);
            formData.append('description', form.value.description || '');
            formData.append('frequency', form.value.frequency || '');
            formData.append('csrfmiddlewaretoken', csrfToken);

            const url = editingId.value
                ? `/institution/api/units/${unitId}/deliverables/save/${editingId.value}/`
                : `/institution/api/units/${unitId}/deliverables/save/`;

            try {
                const res = await fetch(url, {method: 'POST', body: formData});
                if (res.ok) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Guardado',
                        toast: true,
                        position: 'top-end',
                        showConfirmButton: false,
                        timer: 2000
                    });
                    closeModal();
                    await fetchDeliverables();
                }
            } catch (error) {
                console.error("Error al guardar:", error);
            }
        };

        const deleteItem = async (id) => {
            const result = await Swal.fire({
                title: '¿Eliminar entregable?',
                text: "Esta acción no se puede deshacer.",
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#ef4444',
                confirmButtonText: 'Sí, eliminar',
                cancelButtonText: 'Cancelar'
            });

            if (result.isConfirmed) {
                const formData = new FormData();
                formData.append('csrfmiddlewaretoken', csrfToken);
                try {
                    await fetch(`/institution/api/deliverables/delete/${id}/`, {method: 'POST', body: formData});
                    await fetchDeliverables();
                } catch (e) {
                    console.error(e);
                }
            }
        };

        onMounted(() => {
            fetchDeliverables();
        });

        // IMPORTANTE: Todo lo que uses en el HTML debe estar aquí abajo
        return {
            deliverables,
            showModal,
            form,
            editingId,
            openModal,
            closeModal,
            resetForm,
            saveDeliverable,
            deleteItem
        };
    }
}).mount('#deliverables-app');