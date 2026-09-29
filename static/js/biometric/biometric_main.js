/**
 * SIGETH - Módulo de Biométricos
 * Controlador Vanilla JavaScript desacoplado de clases CSS mediante data-actions.
 */

document.addEventListener('DOMContentLoaded', () => {
    const biometricManager = new BiometricManager();
    biometricManager.init();
});

class BiometricManager {
    constructor() {
        this.searchInput = document.getElementById('table-search');
        this.searchTimer = null;
    }

    init() {
        this.bindSearch();
        this.bindActionDelegation();
        this.ensureTableManager();
    }

    ensureTableManager() {
        const table = document.querySelector('.managed-table');
        if (table && window.TableManager && !table._tableManager) {
            new window.TableManager(table);
        }
    }

    bindSearch() {
        if (!this.searchInput) return;

        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.searchTimer);
            this.searchTimer = setTimeout(() => {
                const query = e.target.value.trim();
                window.refreshCurrentTable({q: query, page: 1}, () => {
                    this.ensureTableManager();
                });
            }, 300);
        });
    }

    /**
     * Delegación global de acciones desacoplada de clases CSS
     */
    bindActionDelegation() {
        document.addEventListener('click', (event) => {
            const actionBtn = event.target.closest('[data-action]');
            if (!actionBtn) return;

            const action = actionBtn.dataset.action;

            // 1. Apertura genérica de modales por URL
            if (action === 'open-modal') {
                event.preventDefault();
                const url = actionBtn.dataset.modalUrl;
                if (!url) return;

                window.openAjaxModal(url, (root) => {
                    this.setupInjectedModal(root);
                });
                return;
            }

            // 2. Probar Conexión
            if (action === 'test-connection') {
                event.preventDefault();
                const deviceId = actionBtn.dataset.deviceId;
                const deviceName = actionBtn.dataset.deviceName || 'Dispositivo';
                this.testConnection(deviceId, deviceName);
                return;
            }

            // 3. Descarga Directa
            if (action === 'direct-sync') {
                event.preventDefault();
                const deviceId = actionBtn.dataset.deviceId;
                const deviceName = actionBtn.dataset.deviceName || 'Dispositivo';
                this.loadAttendanceDirect(deviceId, deviceName);
            }
        });
    }

    /**
     * Configuración de formularios inyectados en modal-root
     * @param {HTMLElement} modalRoot
     */
    setupInjectedModal(modalRoot) {
        const form = modalRoot.querySelector('form');

        // Modal de hora
        if (form && form.id === 'biometricTimeForm') {
            this.setupTimeModalListeners(modalRoot);
        }

        // Modal de Usuarios y Migración
        const userFilterInput = modalRoot.querySelector('#modal-user-filter');
        if (userFilterInput) {
            this.setupUsersModalListeners(modalRoot);
        }

        if (form) {
            form.addEventListener('submit', (e) => {
                window.submitAjaxForm(e, () => {
                    window.closeModal();
                    window.refreshCurrentTable({}, () => this.ensureTableManager());
                });
            });
        }
    }

    setupUsersModalListeners(modalRoot) {
        const filterInput = modalRoot.querySelector('#modal-user-filter');
        const rows = modalRoot.querySelectorAll('.user-row');

        // Filtro en vivo en el modal
        filterInput?.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            rows.forEach(row => {
                const pin = row.dataset.pin || '';
                const name = row.dataset.name || '';
                const match = pin.includes(query) || name.includes(query);
                row.style.display = match ? '' : 'none';
            });
        });

        // Botón Migrar por fila
        modalRoot.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-migrate-user');
            if (!btn) return;

            const row = btn.closest('tr');
            const select = row.querySelector('.target-bio-select');
            const targetDeviceId = select?.value;

            if (!targetDeviceId) {
                window.Swal.fire({
                    icon: 'warning',
                    title: 'Selecciona un destino',
                    text: 'Debes elegir el biométrico al cual deseas migrar este usuario.'
                });
                return;
            }

            const payload = {
                target_device_id: targetDeviceId,
                pin: btn.dataset.pin,
                name: btn.dataset.name,
                is_admin: btn.dataset.admin === 'true',
                card: btn.dataset.card,
                password: btn.dataset.password
            };

            const targetName = select.options[select.selectedIndex].text;

            window.Swal.fire({
                title: `¿Migrar a ${targetName}?`,
                html: `Se encolará el usuario <b>${payload.name} (PIN: ${payload.pin})</b> ${payload.is_admin ? '<b style="color:red">(Admin)</b>' : ''} para ser descargado vía ADMS.`,
                icon: 'question',
                showCancelButton: true,
                confirmButtonText: 'Sí, migrar',
                cancelButtonText: 'Cancelar'
            }).then((res) => {
                if (res.isConfirmed) {
                    btn.disabled = true;
                    fetch('/biometric/migrate-user-adms/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': window.getCSRF ? window.getCSRF() : ''
                        },
                        body: JSON.stringify(payload)
                    })
                        .then(r => r.json())
                        .then(data => {
                            btn.disabled = false;
                            if (data.success) {
                                window.Swal.fire({
                                    icon: 'success',
                                    title: 'Encolado con Éxito',
                                    text: data.message
                                });
                            } else {
                                window.Swal.fire({
                                    icon: 'error',
                                    title: 'Error',
                                    text: data.message || 'No se pudo migrar el usuario.'
                                });
                            }
                        })
                        .catch(() => {
                            btn.disabled = false;
                            window.Swal.fire({
                                icon: 'error',
                                title: 'Error de red',
                                text: 'No se pudo comunicar con el servidor.'
                            });
                        });
                }
            });
        });
    }

    /**
     * Listeners específicos para el modal de hora
     */
    setupTimeModalListeners(modalRoot) {
        const form = modalRoot.querySelector('#biometricTimeForm');
        const displayServer = modalRoot.querySelector('#display-server-time');
        const displayDevice = modalRoot.querySelector('#display-device-time');
        const radioManual = modalRoot.querySelector('#radio-mode-manual');
        const radioServer = modalRoot.querySelector('#radio-mode-server');
        const manualGroup = modalRoot.querySelector('#manual-time-group');
        const manualInput = modalRoot.querySelector('#manual_new_time');

        // Extraer id del action del formulario
        const match = form.action.match(/\/(\d+)\/$/);
        const deviceId = match ? match[1] : null;

        if (deviceId) {
            fetch(`/biometric/get-device-time/${deviceId}/`)
                .then(res => res.json())
                .then(data => {
                    if (displayServer) displayServer.textContent = data.server_time || 'Error';
                    if (displayDevice) displayDevice.textContent = data.device_time || 'Error de lectura';
                })
                .catch(() => {
                    if (displayServer) displayServer.textContent = 'Error';
                    if (displayDevice) displayDevice.textContent = 'Sin conexión';
                });
        }

        if (radioManual && radioServer && manualGroup) {
            radioManual.addEventListener('change', () => {
                manualGroup.classList.remove('hidden');
                if (manualInput) manualInput.required = true;
            });
            radioServer.addEventListener('change', () => {
                manualGroup.classList.add('hidden');
                if (manualInput) manualInput.required = false;
            });
        }
    }

    testConnection(deviceId, deviceName) {
        window.showToast(`Probando conexión con ${deviceName}...`, 'info');

        fetch(`/biometric/test-connection/${deviceId}/`)
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    window.Swal.fire({
                        icon: 'success',
                        title: 'Conexión Exitosa',
                        html: `Dispositivo: <b>${deviceName}</b><br>Respuesta correcta del hardware.`
                    });
                    window.refreshCurrentTable({}, () => this.ensureTableManager());
                } else {
                    window.Swal.fire({
                        icon: 'error',
                        title: 'Fallo de Conexión',
                        text: data.message || 'No se pudo comunicar con la IP asignada.'
                    });
                }
            })
            .catch(() => {
                window.Swal.fire({
                    icon: 'error',
                    title: 'Error de Red',
                    text: 'Ocurrió un problema de comunicación con el servidor.'
                });
            });
    }

    loadAttendanceDirect(deviceId, deviceName) {
        window.Swal.fire({
            title: `¿Descargar marcaciones directas?`,
            text: `Se consultarán los registros en ${deviceName}.`,
            icon: 'question',
            showCancelButton: true,
            confirmButtonText: 'Sí, descargar',
            cancelButtonText: 'Cancelar'
        }).then((result) => {
            if (result.isConfirmed) {
                window.showToast('Descargando marcaciones...', 'info');

                fetch(`/biometric/load-attendance/${deviceId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': window.getCSRF ? window.getCSRF() : '',
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                })
                    .then(res => res.json())
                    .then(data => {
                        if (data.status === 'success' || data.success) {
                            window.Swal.fire({
                                icon: 'success',
                                title: 'Descarga Completada',
                                text: data.message
                            });
                        } else {
                            window.Swal.fire({
                                icon: 'error',
                                title: 'Error al Descargar',
                                text: data.message || 'No se pudo completar la descarga.'
                            });
                        }
                    })
                    .catch(() => {
                        window.Swal.fire({
                            icon: 'error',
                            title: 'Error',
                            text: 'Error de comunicación con el biométrico.'
                        });
                    });
            }
        });
    }
}