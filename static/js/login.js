/* static/js/login.js */

document.addEventListener('DOMContentLoaded', () => {
    initPasswordToggle();
    showDjangoMessages();
    initAjaxAuthForms();
});

/**
 * Inicializa el botón para mostrar u ocultar la contraseña en el login.
 */
function initPasswordToggle() {
    const toggleButtons = document.querySelectorAll('.toggle-password');

    toggleButtons.forEach((toggleBtn) => {
        toggleBtn.addEventListener('click', () => {
            const targetId = toggleBtn.dataset.target;
            const passwordInput = targetId
                ? document.getElementById(targetId)
                : toggleBtn.closest('.input-icon-wrapper')?.querySelector('input');

            if (!passwordInput) return;

            const isPassword = passwordInput.getAttribute('type') === 'password';
            passwordInput.setAttribute('type', isPassword ? 'text' : 'password');
            toggleBtn.classList.toggle('fa-eye', !isPassword);
            toggleBtn.classList.toggle('fa-eye-slash', isPassword);
        });
    });
}

/**
 * Muestra mediante SweetAlert2 los mensajes enviados desde Django.
 */
function showDjangoMessages() {
    const messagesScript = document.getElementById('django-messages');
    if (!messagesScript) return;

    let messages = [];
    try {
        messages = JSON.parse(messagesScript.textContent || '[]');
    } catch (e) {
        messages = [];
    }

    if (!Array.isArray(messages)) return;

    messages.forEach((msg) => {
        Swal.fire({
            icon: msg.tag === 'error' ? 'error' : 'success',
            title: msg.tag === 'error' ? 'Error' : 'Éxito',
            text: msg.text,
            confirmButtonColor: '#2c3e50',
            confirmButtonText: 'Entendido',
            showCancelButton: false,
            showDenyButton: false,
            showCloseButton: false,
            allowOutsideClick: false,
            allowEscapeKey: false,
            buttonsStyling: true
        });
    });
}

/**
 * Muestra un modal de carga bloqueante mientras se procesa la solicitud.
 * @param {string} title - Título principal del modal.
 * @param {string} subtitle - Descripción secundaria del proceso.
 */
function showAuthLoadingModal(title, subtitle) {
    Swal.fire({
        html: `
            <div class="loading-wrap">
                <div class="loading-ring"></div>
                <p class="loading-title">${title}</p>
                <p class="loading-subtitle">${subtitle}</p>
            </div>
        `,
        showConfirmButton: false,
        showCancelButton: false,
        allowOutsideClick: false,
        allowEscapeKey: false,
        heightAuto: false,
        scrollbarPadding: false,
        customClass: {
            popup: 'swal2-loading-modern'
        }
    });
}

/**
 * Configura el envío AJAX para los formularios auxiliares de autenticación.
 */
function initAjaxAuthForms() {
    const authForms = document.querySelectorAll('form[data-ajax-auth="true"]');

    authForms.forEach((form) => {
        form.addEventListener('submit', async (event) => {
            event.preventDefault();

            const submitBtn = form.querySelector('button[type="submit"]');
            const actionUrl = form.getAttribute('action') || window.location.href;
            const loadingTitle = form.dataset.loadingTitle || 'Procesando solicitud';
            const loadingSubtitle = form.dataset.loadingSubtitle || 'Por favor espere...';
            const successTitle = form.dataset.successTitle || 'Operación exitosa';

            if (submitBtn) submitBtn.disabled = true;
            showAuthLoadingModal(loadingTitle, loadingSubtitle);

            try {
                const formData = new FormData(form);
                const response = await fetch(actionUrl, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });

                const contentType = response.headers.get('content-type') || '';
                if (!contentType.includes('application/json')) {
                    throw new Error('Respuesta inesperada del servidor.');
                }

                const data = await response.json();
                const isSuccess = response.ok && (data.status === 'success' || data.success === true);
                Swal.close();

                if (!isSuccess) {
                    await Swal.fire({
                        icon: 'error',
                        title: 'No se pudo completar',
                        text: data.message || 'Ocurrió un error al procesar la solicitud.',
                        confirmButtonText: 'Entendido',
                        confirmButtonColor: '#203c7d',
                        showCancelButton: false,
                        heightAuto: false,
                        scrollbarPadding: false
                    });
                    return;
                }

                await Swal.fire({
                    icon: 'success',
                    title: successTitle,
                    text: data.message || 'Proceso completado correctamente.',
                    confirmButtonText: 'Entendido',
                    confirmButtonColor: '#203c7d',
                    showCancelButton: false,
                    heightAuto: false,
                    scrollbarPadding: false
                });

                if (data.redirect_url) {
                    window.location.href = data.redirect_url;
                } else {
                    form.reset();
                }
            } catch (error) {
                Swal.close();
                await Swal.fire({
                    icon: 'error',
                    title: 'Error de conexión',
                    text: 'No se pudo completar la solicitud. Inténtelo nuevamente.',
                    confirmButtonText: 'Entendido',
                    confirmButtonColor: '#203c7d',
                    showCancelButton: false,
                    heightAuto: false,
                    scrollbarPadding: false
                });
            } finally {
                if (submitBtn) submitBtn.disabled = false;
            }
        });
    });
}