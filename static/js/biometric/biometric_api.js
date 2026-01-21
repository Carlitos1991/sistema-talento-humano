/**
 * Service para manejar todas las peticiones fetch de Biométricos
 */
const BiometricService = {
    async getTable(query = '') {
        const response = await fetch(`?q=${query}`, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        if (!response.ok) throw new Error('Error al cargar la tabla');
        return await response.json();
    },

    async save(data) {
        const url = data.id ? `/biometric/update/${data.id}/` : '/biometric/create/';
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify(data)
        });
        return await response.json();
    },

    getCsrfToken() {
        return document.cookie.split('; ')
            .find(row => row.startsWith('csrftoken='))
            ?.split('=')[1];
    }
};