/* static/js/login.js */

document.addEventListener('DOMContentLoaded', () => {

    // ------------------------------------------------
    // 1. Toggle Password (Vanilla JS, sin Vue)
    // ------------------------------------------------
    const toggleBtn = document.querySelector('.toggle-password');
    const passwordInput = document.querySelector('input[name="password"]');

    if (toggleBtn && passwordInput) {
        toggleBtn.addEventListener('click', () => {
            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            toggleBtn.classList.toggle('fa-eye', !isPassword);
            toggleBtn.classList.toggle('fa-eye-slash', isPassword);
        });
    }

    // ------------------------------------------------
    // 2. Lógica SweetAlert (Mensajes desde Django)
    // ------------------------------------------------
    const messagesScript = document.getElementById('django-messages');

    if (messagesScript) {
        let messages = [];
        try {
            messages = JSON.parse(messagesScript.textContent || '[]');
        } catch (e) {
            messages = [];
        }

        if (Array.isArray(messages)) {
            messages.forEach(msg => {
                Swal.fire({
                    icon: msg.tag === 'error' ? 'error' : 'success',
                    title: msg.tag === 'error' ? 'Error' : 'Éxito',
                    text: msg.text,
                    confirmButtonColor: '#2c3e50',
                    confirmButtonText: 'Entendido',
                    cancelButtonText: 'Cancelar',
                    showCancelButton: false,
                    showDenyButton: false,
                    showCloseButton: false,
                    allowOutsideClick: false,
                    allowEscapeKey: false,
                    buttonsStyling: true
                });
            });
        }
    }
});