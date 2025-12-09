/* static/js/login.js */

document.addEventListener('DOMContentLoaded', () => {

    // ------------------------------------------------
    // 1. Lógica VUE.js (Toggle Password)
    // ------------------------------------------------
    const {createApp, ref} = Vue;

    if (document.getElementById('loginApp')) {
        createApp({
            setup() {
                const passwordVisible = ref(false);
                const togglePassword = () => {
                    passwordVisible.value = !passwordVisible.value;
                };
                return {passwordVisible, togglePassword};
            }
        }).mount('#loginApp');
    }

    // ------------------------------------------------
    // 2. Lógica SweetAlert (Mensajes desde Django)
    // ------------------------------------------------
    // Buscamos el script JSON que contiene los mensajes (Patrón Data Island)
    const messagesScript = document.getElementById('django-messages');

    if (messagesScript) {
        // Parseamos el contenido JSON
        const messages = JSON.parse(messagesScript.textContent);

        // Iteramos y mostramos alertas
        messages.forEach(msg => {
            Swal.fire({
                icon: msg.tag === 'error' ? 'error' : 'success',
                title: msg.tag === 'error' ? 'Error' : 'Éxito',
                text: msg.text,
                confirmButtonColor: '#2c3e50',
                confirmButtonText: 'Entendido'
            });
        });
    }
});