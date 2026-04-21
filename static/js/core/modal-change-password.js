// Modal: Cambiar Contraseña - Lógica

let __forceChangeRequired = false;

function openChangePasswordModal() {
    const modal = document.getElementById('changePasswordModal');
    if (modal) {
        modal.classList.remove('hidden');
        // asegurar visibilidad si reglas CSS externas siguen ocultando el elemento
        try {
            modal.style.display = modal.style.display || 'flex';
            modal.style.visibility = 'visible';
            modal.style.zIndex = modal.style.zIndex || '2147483647';
        } catch (e) { /* ignore */ }
        const pw = document.getElementById('newPassword');
        if (pw) pw.focus();
        // Cerrar el dropdown del navbar
        const dropdown = document.querySelector('.dropdown-menu');
        if (dropdown) dropdown.classList.add('hidden');
    }
}

function closeChangePasswordModal(forceOverride = false) {
    // Bloquea cierre solo si el servidor o el body indican que el cambio es obligatorio.
    if (!forceOverride) {
        try {
            const serverFlag = (typeof window !== 'undefined' && !!window.__serverForceChange);
            const bodyFlag = (document && document.body && document.body.getAttribute && document.body.getAttribute('data-force-change') === '1');
            const params = (typeof window !== 'undefined' && window.location) ? new URLSearchParams(window.location.search) : null;
            const urlFlag = params && params.get('force') === '1';

            if (serverFlag || bodyFlag || urlFlag) {
                // El servidor exige el cambio: bloqueamos el cierre a menos que forceOverride === true
                return;
            }
        } catch (e) {
            // En caso de error al evaluar flags, no bloqueamos el cierre para evitar UX bloqueada.
        }
    }
    const modal = document.getElementById('changePasswordModal');
    if (modal) {
        modal.classList.add('hidden');
        // Limpiar formulario
        document.getElementById('changePasswordForm').reset();
        document.getElementById('passwordMatchMessage').style.display = 'none';
        document.getElementById('submitChangePasswordBtn').disabled = true;
    }
}

// Validación de requisitos de contraseña
function validatePasswordRequirements(password) {
    const requirements = {
        length: password.length >= 8,
        lowercase: /[a-z]/.test(password),
        number: /[0-9]/.test(password)
    };

    // Actualizar UI de requisitos
    const reqLength = document.getElementById('req-length');
    const reqLowercase = document.getElementById('req-lowercase');
    const reqNumber = document.getElementById('req-number');

    if (requirements.length) {
        reqLength.classList.remove('text-danger');
        reqLength.classList.add('req-met');
    } else {
        reqLength.classList.add('text-danger');
        reqLength.classList.remove('req-met');
    }

    if (requirements.lowercase) {
        reqLowercase.classList.remove('text-danger');
        reqLowercase.classList.add('req-met');
    } else {
        reqLowercase.classList.add('text-danger');
        reqLowercase.classList.remove('req-met');
    }

    if (requirements.number) {
        reqNumber.classList.remove('text-danger');
        reqNumber.classList.add('req-met');
    } else {
        reqNumber.classList.add('text-danger');
        reqNumber.classList.remove('req-met');
    }

    return requirements;
}

// Validación de coincidencia de contraseñas
function validatePasswordMatch() {
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const matchMessage = document.getElementById('passwordMatchMessage');
    const matchText = document.getElementById('matchText');

    if (confirmPassword === '') {
        matchMessage.style.display = 'none';
        return false;
    }

    const matches = newPassword === confirmPassword;
    matchMessage.style.display = 'block';
    
    if (matches) {
        matchText.textContent = '✓ Las contraseñas coinciden';
        matchText.style.color = '#10b981';
        document.getElementById('confirmPassword').classList.remove('error');
    } else {
        matchText.textContent = '✗ Las contraseñas no coinciden';
        matchText.style.color = '#ef4444';
        document.getElementById('confirmPassword').classList.add('error');
    }

    return matches;
}

// Actualizar estado del botón enviar
function updateSubmitButton() {
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const submitBtn = document.getElementById('submitChangePasswordBtn');

    const requirements = validatePasswordRequirements(newPassword);
    const allMet = requirements.length && requirements.lowercase && requirements.number && 
                  newPassword === confirmPassword;

    submitBtn.disabled = !allMet;
}

// Validación en tiempo real
document.addEventListener('DOMContentLoaded', function() {
    const newPasswordInput = document.getElementById('newPassword');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    const submitBtn = document.getElementById('submitChangePasswordBtn');

    if (newPasswordInput) {
        newPasswordInput.addEventListener('input', function() {
            validatePasswordRequirements(this.value);
            validatePasswordMatch();
            updateSubmitButton();
        });
    }

    if (confirmPasswordInput) {
        confirmPasswordInput.addEventListener('input', function() {
            validatePasswordMatch();
            updateSubmitButton();
        });
    }

    // Cerrar modal al hacer clic fuera
    const modal = document.getElementById('changePasswordModal');
    if (modal) {
        modal.addEventListener('click', function(event) {
            if (event.target === modal) {
                // solo cerrar si NO es obligatorio el cambio
                closeChangePasswordModal();
            }
        });
    }

    // Cerrar modal con tecla Escape
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeChangePasswordModal();
        }
    });
});

// Auto-open si la URL contiene ?force=1 o si el servidor indicó con data-force-change
document.addEventListener('DOMContentLoaded', function () {
    console.debug('[modal-change-password] DOMContentLoaded - checking force flags');
    try {
        const params = new URLSearchParams(window.location.search);
        if (params.get('force') === '1') {
            __forceChangeRequired = true;
            console.debug('[modal-change-password] detected URL param force=1');
        }
    } catch (e) { /* ignore */ }

    try {
        if (!__forceChangeRequired && document && document.body && document.body.dataset && document.body.dataset.forceChange === '1') {
            __forceChangeRequired = true;
            console.debug('[modal-change-password] detected body data-force-change=1');
        }
    } catch (e) { /* ignore */ }

    if (__forceChangeRequired) {
        console.debug('[modal-change-password] forcing modal open (forceRequired=true)');
        // Abrir modal y desactivar botones de cierre
        openChangePasswordModal();
        const closeBtn = document.querySelector('#changePasswordModal .modal-close');
        if (closeBtn) closeBtn.style.display = 'none';
        const cancelBtn = document.querySelector('#changePasswordModal .btn-cancel');
        if (cancelBtn) cancelBtn.style.display = 'none';

        // Evitar cerrar por overlay o Escape: handlers ya consultan __forceChangeRequired
    }
});

// --- Ejecutar comprobación inmediata (útil si el script se carga después de DOMContentLoaded o filtros de consola)
(function immediateCheck() {
    try {
        // Preferir la variable expuesta por el servidor
        const serverFlag = (typeof window !== 'undefined' && window.__serverForceChange) ? true : false;
        const params = (typeof window !== 'undefined' && window.location) ? new URLSearchParams(window.location.search) : null;
        const urlFlag = params && params.get('force') === '1';

        if (serverFlag || urlFlag || (document && document.body && document.body.getAttribute && document.body.getAttribute('data-force-change') === '1')) {
            console.info('[modal-change-password] immediateCheck: will open modal (serverFlag, urlFlag)=', serverFlag, urlFlag);
            __forceChangeRequired = true;
            openChangePasswordModal();
            const closeBtn = document.querySelector('#changePasswordModal .modal-close');
            if (closeBtn) closeBtn.style.display = 'none';
            const cancelBtn = document.querySelector('#changePasswordModal .btn-cancel');
            if (cancelBtn) cancelBtn.style.display = 'none';
        }
    } catch (e) {
        console.warn('[modal-change-password] immediateCheck error', e);
    }
})();

// Si el flag del servidor se asigna después de cargar este script, hacemos
// una comprobación corta por intervalos y observamos cambios en el atributo
// `data-force-change` del <body> para garantizar que abrimos el modal.
(function watchForLateServerFlag() {
    try {
        // Si ya forzado, no necesitamos hacer nada
        if (typeof __forceChangeRequired !== 'undefined' && __forceChangeRequired) return;

        let checks = 0;
        const maxChecks = 10; // comprobar ~2s en total
        const intervalMs = 200;

        const checker = setInterval(() => {
            const serverFlag = !!(window && window.__serverForceChange);
            const bodyFlag = (document && document.body && document.body.getAttribute && document.body.getAttribute('data-force-change') === '1');
            if (serverFlag || bodyFlag) {
                console.info('[modal-change-password] late-detect: opening modal (serverFlag, bodyFlag)=', serverFlag, bodyFlag);
                __forceChangeRequired = true;
                openChangePasswordModal();
                const closeBtn = document.querySelector('#changePasswordModal .modal-close');
                if (closeBtn) closeBtn.style.display = 'none';
                const cancelBtn = document.querySelector('#changePasswordModal .btn-cancel');
                if (cancelBtn) cancelBtn.style.display = 'none';
                clearInterval(checker);
                observer && observer.disconnect();
                return;
            }

            checks += 1;
            if (checks >= maxChecks) {
                clearInterval(checker);
            }
        }, intervalMs);

        // Observar cambios en atributos del body (por si otro script asigna data-force-change)
        const observer = (typeof MutationObserver !== 'undefined' && document && document.body) ? new MutationObserver(mutations => {
            for (const m of mutations) {
                if (m.type === 'attributes' && m.attributeName === 'data-force-change') {
                    const val = document.body.getAttribute('data-force-change');
                    if (val === '1') {
                        console.info('[modal-change-password] MutationObserver detected data-force-change=1');
                        __forceChangeRequired = true;
                        openChangePasswordModal();
                        const closeBtn = document.querySelector('#changePasswordModal .modal-close');
                        if (closeBtn) closeBtn.style.display = 'none';
                        const cancelBtn = document.querySelector('#changePasswordModal .btn-cancel');
                        if (cancelBtn) cancelBtn.style.display = 'none';
                        clearInterval(checker);
                        observer.disconnect();
                        break;
                    }
                }
            }
        }) : null;

        if (observer) {
            observer.observe(document.body, { attributes: true });
        }
    } catch (e) {
        console.warn('[modal-change-password] watchForLateServerFlag error', e);
    }
})();

// Enviar formulario
function submitChangePassword() {
    const form = document.getElementById('changePasswordForm');
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    // Validación final
    if (newPassword !== confirmPassword) {
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Las contraseñas no coinciden.',
            confirmButtonText: 'OK'
        });
        return;
    }

    // Hacer petición AJAX
    const formData = new FormData(form);
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/change-password/', {
        method: 'POST',
        headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest'
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            Swal.fire({
                icon: 'success',
                title: 'Éxito',
                text: 'Tu contraseña ha sido cambiada correctamente.',
                confirmButtonText: 'OK'
            }).then(() => {
                // Forzar cierre aunque había bloqueo obligatorio (se debe haber actualizado el flag en el servidor)
                closeChangePasswordModal(true);
            });
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Error',
                text: data.message || 'Ocurrió un error al cambiar la contraseña.',
                confirmButtonText: 'OK'
            });
        }
    })
    .catch(error => {
        console.error('Error:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Error de conexión. Intenta de nuevo.',
            confirmButtonText: 'OK'
        });
    });
}
