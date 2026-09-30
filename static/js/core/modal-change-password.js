document.addEventListener('DOMContentLoaded', function () {
    const newPass = document.getElementById('newPassword');
    const confirmPass = document.getElementById('confirmPassword');
    const submitBtn = document.getElementById('submitChangePasswordBtn');
    const form = document.getElementById('changePasswordForm');

    if (!newPass || !confirmPass) return;

    function validate() {
        const val = newPass.value;
        const confirmVal = confirmPass.value;

        const hasLength = val.length >= 8;
        const hasLower = /[a-z]/.test(val);
        const hasNumber = /[0-9]/.test(val);
        const matches = val.length > 0 && val === confirmVal;

        updateRequirement('req-length', hasLength);
        updateRequirement('req-lowercase', hasLower);
        updateRequirement('req-number', hasNumber);

        const matchMsg = document.getElementById('passwordMatchMessage');
        const matchText = document.getElementById('matchText');
        if (confirmVal.length > 0) {
            matchMsg.style.display = 'block';
            if (matches) {
                matchText.textContent = 'Las contraseñas coinciden';
                matchText.className = 'text-success small fw-bold';
            } else {
                matchText.textContent = 'Las contraseñas no coinciden';
                matchText.className = 'text-danger small fw-bold';
            }
        } else {
            matchMsg.style.display = 'none';
        }

        if (submitBtn) {
            submitBtn.disabled = !(hasLength && hasLower && hasNumber && matches);
        }
    }

    function updateRequirement(elId, isValid) {
        const el = document.getElementById(elId);
        if (!el) return;
        if (isValid) {
            el.className = 'text-success mb-1';
            el.querySelector('i').className = 'fa-solid fa-circle-check me-1';
        } else {
            el.className = 'text-danger mb-1';
            el.querySelector('i').className = 'fa-solid fa-circle-xmark me-1';
        }
    }

    newPass.addEventListener('input', validate);
    confirmPass.addEventListener('input', validate);

    if (form) {
        form.addEventListener('submit', function (e) {
            e.preventDefault();
            const formData = new FormData(form);

            fetch(form.action, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                },
                body: formData
            })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        Swal.fire({
                            icon: 'success',
                            title: '¡Éxito!',
                            text: data.message,
                            timer: 2000,
                            showConfirmButton: false
                        }).then(() => {
                            window.location.reload();
                        });
                    } else {
                        Swal.fire({
                            icon: 'warning',
                            title: 'Atención',
                            text: data.message
                        });
                    }
                })
                .catch(err => {
                    Swal.fire({
                        icon: 'error',
                        title: 'Error',
                        text: 'No se pudo actualizar la contraseña.'
                    });
                });
        });
    }

    // Si tiene la sesión forzada abierta, mostrar el modal inmediatamente
    if (document.body.dataset.forceChange === '1') {
        const modal = document.getElementById('changePasswordModal');
        if (modal) modal.classList.remove('hidden');
    }
});

function closeChangePasswordModal() {
    const modal = document.getElementById('changePasswordModal');
    if (modal) modal.classList.add('hidden');
}