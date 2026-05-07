document.addEventListener('DOMContentLoaded', function () {
    const urlList = document.getElementById('url-list').value;
    const notificationsWrapper = document.getElementById('latest-notifications-wrapper');
    const notificationsMonthSelect = document.getElementById('notifications-month');
    const notificationsYearInput = document.getElementById('notifications-year');
    const modalOverlay = document.getElementById('customModal');
    const modalContentContainer = document.getElementById('modal-dynamic-content');

    if (notificationsMonthSelect) {
        notificationsMonthSelect.addEventListener('change', () => fetchNotificationsPage(1));
    }

    if (notificationsYearInput) {
        notificationsYearInput.addEventListener('change', () => fetchNotificationsPage(1));
    }

    bindNotificationPagination();
    bindNotificationEditButtons();

    if (modalOverlay) {
        modalOverlay.addEventListener('click', (e) => {
            if (e.target === modalOverlay || e.target.closest('.btn-close-modal') || e.target.closest('.js-close-modal')) {
                closeModal();
            }
        });
    }

    if (modalContentContainer) {
        modalContentContainer.addEventListener('click', function (e) {
            const listBtn = e.target.closest('.js-open-notification-list');
            if (listBtn) {
                e.preventDefault();
                // Si tienes esta función, implementala, de lo contrario la ignorará.
                return;
            }

            const editNotificationBtn = e.target.closest('.js-edit-notification');
            if (editNotificationBtn) {
                e.preventDefault();
                openGenerateNotificationModal(
                    editNotificationBtn.dataset.employeeId,
                    editNotificationBtn.dataset.notificationId || ''
                );
                return;
            }
        });
    }

    function openGenerateNotificationModal(employeeId, notificationId = '') {
        const params = new URLSearchParams();
        if (employeeId) {
            params.set('employee_id', employeeId);
        }
        if (notificationId) {
            params.set('notification_id', notificationId);
        }
        const url = `/sanctions/notifications/generate/?${params.toString()}`;

        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(res => res.text())
            .then(html => {
                modalContentContainer.innerHTML = html;
                modalOverlay.classList.remove('hidden');
                document.body.classList.add('modal-open');

                initModalPlugins();

                const form = modalContentContainer.querySelector('#generateNotificationForm');
                if (form) form.addEventListener('submit', handleNotificationFormSubmit);
            })
            .catch(err => {
                console.error('Error al abrir modal de notificación:', err);
                Swal.fire('Error', 'No se pudo cargar el formulario de notificación', 'error');
            });
    }

    function handleNotificationFormSubmit(e) {
        e.preventDefault();
        const form = e.target;
        const formData = new FormData(form);

        form.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
        form.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');

        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {'X-Requested-With': 'XMLHttpRequest'}
        })
            .then(async res => {
                const data = await res.json().catch(() => ({}));

                if (res.ok && data.success) {
                    closeModal();
                    const Toast = Swal.mixin({
                        toast: true,
                        position: 'top-end',
                        showConfirmButton: false,
                        timer: 3000,
                        timerProgressBar: true
                    });
                    Toast.fire({icon: 'success', title: data.message || 'Notificación generada correctamente'});

                    const currentNotificationsPage = parseInt(document.getElementById('notifications-page-input')?.value) || 1;
                    fetchNotificationsPage(currentNotificationsPage);
                    return;
                }

                if (res.status === 403) {
                    Swal.fire('Acceso denegado', data.message || 'No tiene permisos para realizar esta acción', 'error');
                } else if (data.errors) {
                    showErrors(form, data.errors);
                } else {
                    Swal.fire('Error', data.message || 'Ocurrió un error al generar la notificación', 'error');
                }
            })
            .catch(err => {
                console.error(err);
                Swal.fire('Error', 'Error de comunicación con el servidor', 'error');
            });
    }

    function closeModal() {
        if(modalOverlay) modalOverlay.classList.add('hidden');
        if(modalContentContainer) modalContentContainer.innerHTML = '';
        document.body.classList.remove('modal-open');
    }

    function fetchNotificationsPage(page) {
        const params = new URLSearchParams();
        params.set('notifications_page', page);
        if (notificationsMonthSelect && notificationsMonthSelect.value) {
            params.set('notifications_month', notificationsMonthSelect.value);
        }
        if (notificationsYearInput && notificationsYearInput.value) {
            params.set('notifications_year', notificationsYearInput.value);
        }

        fetch(`${urlList}?${params.toString()}`, {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(res => res.json())
        .then(data => {
            if (notificationsWrapper && data.html) {
                notificationsWrapper.innerHTML = data.html;
                bindNotificationPagination();
                bindNotificationEditButtons();
            }
        })
        .catch(err => console.error('Error fetching notifications:', err));
    }

    function initModalPlugins() {
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.select2').select2({
                width: '100%',
                dropdownParent: modalOverlay
            });
        }
        // ... (resto de initModalPlugins omitido por brevedad, igual al de sanction_employee.js si se requiere)
    }

    function bindNotificationEditButtons() {
        document.querySelectorAll('.js-edit-notification').forEach((button) => {
            if (button.dataset.bound === '1') {
                return;
            }

            button.addEventListener('click', (event) => {
                event.preventDefault();
                openGenerateNotificationModal(
                    button.dataset.employeeId || '',
                    button.dataset.notificationId || ''
                );
            });

            button.dataset.bound = '1';
        });
    }

    function bindNotificationPagination() {
        const notificationsFirst = document.getElementById('notifications-btn-first');
        const notificationsPrev = document.getElementById('notifications-btn-prev');
        const notificationsNext = document.getElementById('notifications-btn-next');
        const notificationsLast = document.getElementById('notifications-btn-last');
        const notificationsPageInput = document.getElementById('notifications-page-input');

        if (notificationsFirst && notificationsFirst.dataset.bound !== '1') {
            notificationsFirst.addEventListener('click', () => fetchNotificationsPage(1));
            notificationsFirst.dataset.bound = '1';
        }

        if (notificationsPrev && notificationsPrev.dataset.bound !== '1') {
            notificationsPrev.addEventListener('click', () => {
                const current = parseInt(notificationsPageInput ? notificationsPageInput.value : '1', 10) || 1;
                if (current > 1) {
                    fetchNotificationsPage(current - 1);
                }
            });
            notificationsPrev.dataset.bound = '1';
        }

        if (notificationsNext && notificationsNext.dataset.bound !== '1') {
            notificationsNext.addEventListener('click', () => {
                const current = parseInt(notificationsPageInput ? notificationsPageInput.value : '1', 10) || 1;
                const total = parseInt(notificationsPageInput ? notificationsPageInput.max : '1', 10) || 1;
                if (current < total) {
                    fetchNotificationsPage(current + 1);
                }
            });
            notificationsNext.dataset.bound = '1';
        }

        if (notificationsLast && notificationsLast.dataset.bound !== '1') {
            notificationsLast.addEventListener('click', () => {
                const total = parseInt(notificationsPageInput ? notificationsPageInput.max : '1', 10) || 1;
                fetchNotificationsPage(total);
            });
            notificationsLast.dataset.bound = '1';
        }

        if (notificationsPageInput && notificationsPageInput.dataset.bound !== '1') {
            notificationsPageInput.addEventListener('change', () => {
                const targetPage = parseInt(notificationsPageInput.value, 10);
                const total = parseInt(notificationsPageInput.max, 10) || 1;
                if (!Number.isNaN(targetPage)) {
                    const safePage = Math.min(Math.max(targetPage, 1), total);
                    fetchNotificationsPage(safePage);
                }
            });
            notificationsPageInput.dataset.bound = '1';
        }
    }
    
    function showErrors(form, errors) {
        for (const [field, msgs] of Object.entries(errors)) {
            const input = form.querySelector(`[name="${field}"]`);
            if (input) {
                input.classList.add('is-invalid');
                const feedback = input.parentNode.querySelector('.invalid-feedback');
                if (feedback) feedback.textContent = Array.isArray(msgs) ? msgs.join(', ') : msgs;
            }
        }
    }
});