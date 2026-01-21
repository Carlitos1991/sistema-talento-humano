/**
 * Service para manejar todas las peticiones fetch de Biométricos
 */
const BiometricService = {
    async getTable(query = '') {
        const response = await fetch(`${window.location.pathname}?q=${query}`, {
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        if (!response.ok) throw new Error('Error al cargar la tabla');
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