// Modal: Cambiar Contraseña - Lógica

function openChangePasswordModal() {
    const modal = document.getElementById('changePasswordModal');
    if (modal) {
        modal.classList.remove('hidden');
        document.getElementById('newPassword').focus();
        // Cerrar el dropdown del navbar
        const dropdown = document.querySelector('.dropdown-menu');
        if (dropdown) dropdown.classList.add('hidden');
    }
}

function closeChangePasswordModal() {
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
    document.getElementById('req-length').classList.toggle('req-met', requirements.length);
    document.getElementById('req-lowercase').classList.toggle('req-met', requirements.lowercase);
    document.getElementById('req-number').classList.toggle('req-met', requirements.number);

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
                closeChangePasswordModal();
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
