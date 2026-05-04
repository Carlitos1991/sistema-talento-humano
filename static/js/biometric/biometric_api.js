/**
 * Service para manejar todas las peticiones fetch de Biométricos
 */
const BiometricService = {
    async getTable(query = '', status = '', page = 1, sort_field = '', sort_dir = '') {
        const params = new URLSearchParams();
        if (query) params.append('q', query);
        if (status) params.append('status', status);
        if (page) params.append('page', page);
        if (sort_field) params.append('sort_field', sort_field);
        if (sort_dir) params.append('sort_dir', sort_dir);
        const url = `${window.location.pathname}?${params.toString()}`;

        const response = await fetch(url, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        if (!response.ok) throw new Error('Error al cargar la tabla');
        return await response.json();
    },
    async testConnection(id) {
        const url = `/biometric/test-connection/${id}/`;
        const response = await fetch(url);
        if (!response.ok) throw new Error('Error en la comunicación');
        return await response.json();
    },

    async save(data) {
        const url = '/biometric/save-ajax/'; // Ruta única sincronizada con urls.py

        // Usamos FormData para que Django procese request.POST correctamente
        const formData = new FormData();
        if (data.id) formData.append('id', data.id);
        formData.append('name', data.name);
        formData.append('ip_address', data.ip_address);
        formData.append('port', data.port);
        formData.append('location', data.location);
        formData.append('is_active', data.is_active);
        formData.append('serial_number', data.serial_number || '');
        formData.append('model_name', data.model_name || '');

        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCsrfToken()
            },
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.message || 'Error en la solicitud');
        }

        return await response.json();
    },

    getCsrfToken() {
        return document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
    }
};