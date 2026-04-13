(function () {
    const appNode = document.getElementById('offline-app') || document.getElementById('offline-app-embedded');

    if (!appNode) {
        return;
    }

    const suffix = appNode.id === 'offline-app-embedded' ? '-embedded' : '';

    const byId = (baseId) => document.getElementById(`${baseId}${suffix}`);

    const config = {
        syncUrl: appNode.dataset.syncUrl || '/biometric/offline-attendance/sync/',
        swUrl: appNode.dataset.swUrl || '/biometric/offline-attendance/sw.js',
        pageUrl: appNode.dataset.pageUrl || '/biometric/offline-attendance/',
        employeeName: appNode.dataset.employeeName || '',
        employeeDocument: appNode.dataset.employeeDocument || '',
        canSync: appNode.dataset.canSync === 'true'
    };

    const dbName = 'sigeth_offline_attendance';
    const dbVersion = 1;
    const storeName = 'attendance_queue';
    const isStandaloneMode = appNode.id === 'offline-app';

    const pendingCountNode = byId('pending-count');
    const recordListNode = byId('record-list');
    const statusNoteNode = byId('status-note');
    const connectionPillNode = byId('connection-pill');
    const gpsWarningNode = byId('gps-warning');
    const btnIncome = byId('btn-income');
    const btnExit = byId('btn-exit');
    const btnSync = byId('btn-sync');
    const pinSetupBox = byId('pin-setup-box');
    const pinUnlockBox = byId('pin-unlock-box');
    const pinNewInput = byId('pin-new');
    const pinConfirmInput = byId('pin-confirm');
    const pinSetBtn = byId('pin-set-btn');
    const pinInput = byId('pin-input');
    const pinUnlockBtn = byId('pin-unlock-btn');
    const pinResetBtn = byId('pin-reset-btn');
    const biometricSetupBtn = byId('biometric-setup-btn');
    const biometricUnlockBtn = byId('biometric-unlock-btn');
    const pinMessageNode = byId('pin-message');

    let databasePromise = null;
    let syncInProgress = false;
    let accessUnlocked = false;

    const pinIdentity = (config.employeeDocument || config.employeeName || 'anonimo')
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .slice(0, 64);
    const pinProfileStorageKey = `sigeth_pin_profile_${pinIdentity}`;
    const pinSessionStorageKey = `sigeth_pin_unlock_${pinIdentity}`;
    const unlockSessionTtlMs = 1000 * 60 * 60 * 12;
    const webAuthnAvailable = !!(window.PublicKeyCredential && navigator.credentials);

    function setStatus(message, type) {
        if (statusNoteNode) {
            statusNoteNode.textContent = message;
        }

        if (connectionPillNode) {
            connectionPillNode.textContent = type === 'online' ? 'En línea' : (type === 'offline' ? 'Sin conexión' : 'Verificando conexión');
            connectionPillNode.style.background = type === 'online' ? 'rgba(34, 197, 94, 0.14)' : type === 'offline' ? 'rgba(239, 68, 68, 0.14)' : 'rgba(20, 184, 166, 0.12)';
            connectionPillNode.style.color = type === 'online' ? '#bbf7d0' : type === 'offline' ? '#fecaca' : '#a7f3d0';
            connectionPillNode.style.borderColor = type === 'online' ? 'rgba(34, 197, 94, 0.22)' : type === 'offline' ? 'rgba(239, 68, 68, 0.22)' : 'rgba(20, 184, 166, 0.22)';
        }
    }

    function setPinMessage(message, tone) {
        if (!pinMessageNode) {
            return;
        }

        pinMessageNode.textContent = message;

        if (tone === 'error') {
            pinMessageNode.style.background = 'rgba(239, 68, 68, 0.14)';
            pinMessageNode.style.borderColor = 'rgba(239, 68, 68, 0.28)';
            pinMessageNode.style.color = '#fecaca';
            return;
        }

        if (tone === 'success') {
            pinMessageNode.style.background = 'rgba(34, 197, 94, 0.14)';
            pinMessageNode.style.borderColor = 'rgba(34, 197, 94, 0.28)';
            pinMessageNode.style.color = '#bbf7d0';
            return;
        }

        pinMessageNode.style.background = 'rgba(20, 184, 166, 0.11)';
        pinMessageNode.style.borderColor = 'rgba(20, 184, 166, 0.30)';
        pinMessageNode.style.color = '#99f6e4';
    }

    function showAlert(icon, title, text) {
        if (window.Swal && typeof window.Swal.fire === 'function') {
            return window.Swal.fire({
                icon,
                title,
                text,
                confirmButtonText: 'Aceptar',
                customClass: {
                    confirmButton: 'btn-swal-confirm-green-centered'
                },
                buttonsStyling: false
            });
        }

        return Promise.resolve();
    }

    function setElementEnabled(element, enabled) {
        if (!element) {
            return;
        }
        element.disabled = !enabled;
        element.classList.toggle('is-disabled', !enabled);
    }

    function setActionsEnabled(enabled) {
        setElementEnabled(btnIncome, enabled);
        setElementEnabled(btnExit, enabled);
        setElementEnabled(btnSync, enabled && config.canSync);
    }

    function loadPinProfile() {
        try {
            const raw = localStorage.getItem(pinProfileStorageKey);
            if (!raw) {
                return null;
            }
            const parsed = JSON.parse(raw);
            if (!parsed || !parsed.pinHash || !parsed.pinSalt) {
                return null;
            }
            return parsed;
        } catch (error) {
            return null;
        }
    }

    function savePinProfile(profile) {
        localStorage.setItem(pinProfileStorageKey, JSON.stringify(profile));
    }

    function isPinFormatValid(pin) {
        return /^\d{4,8}$/.test(pin || '');
    }

    function generateSalt() {
        const bytes = new Uint8Array(16);
        crypto.getRandomValues(bytes);
        return Array.from(bytes).map((value) => value.toString(16).padStart(2, '0')).join('');
    }

    async function hashPin(pin, salt) {
        if (!window.crypto || !window.crypto.subtle) {
            return btoa(`${salt}:${pin}`).replace(/=/g, '');
        }

        const text = `${salt}:${pin}`;
        const data = new TextEncoder().encode(text);
        const hashBuffer = await crypto.subtle.digest('SHA-256', data);
        return Array.from(new Uint8Array(hashBuffer)).map((value) => value.toString(16).padStart(2, '0')).join('');
    }

    function markSessionUnlocked(value) {
        if (!value) {
            sessionStorage.removeItem(pinSessionStorageKey);
            return;
        }

        sessionStorage.setItem(pinSessionStorageKey, JSON.stringify({at: Date.now()}));
    }

    function isSessionUnlocked() {
        try {
            const raw = sessionStorage.getItem(pinSessionStorageKey);
            if (!raw) {
                return false;
            }
            const parsed = JSON.parse(raw);
            if (!parsed || !parsed.at) {
                return false;
            }
            return (Date.now() - Number(parsed.at)) <= unlockSessionTtlMs;
        } catch (error) {
            return false;
        }
    }

    function toBase64Url(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let index = 0; index < bytes.byteLength; index += 1) {
            binary += String.fromCharCode(bytes[index]);
        }
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }

    function fromBase64Url(value) {
        const padded = value.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((value.length + 3) % 4);
        const binary = atob(padded);
        const bytes = new Uint8Array(binary.length);
        for (let index = 0; index < binary.length; index += 1) {
            bytes[index] = binary.charCodeAt(index);
        }
        return bytes.buffer;
    }

    function randomChallenge() {
        const challenge = new Uint8Array(32);
        crypto.getRandomValues(challenge);
        return challenge;
    }

    function applyAccessState(unlocked) {
        accessUnlocked = unlocked;
        setActionsEnabled(unlocked);

        if (isStandaloneMode) {
            appNode.classList.toggle('is-locked', !unlocked);
        }

        if (pinUnlockBox) {
            pinUnlockBox.style.opacity = unlocked ? '0.72' : '1';
        }

        if (unlocked) {
            setPinMessage('Bitácora desbloqueada. Puedes registrar ingreso y salida.', 'success');
            return;
        }

        setPinMessage('Debes desbloquear con PIN para registrar marcaciones.', 'info');
    }

    function refreshAuthUi() {
        const profile = loadPinProfile();
        const hasPin = !!profile;

        if (pinSetupBox) {
            pinSetupBox.style.display = 'block';
        }

        if (pinUnlockBox) {
            pinUnlockBox.style.display = hasPin ? 'block' : 'none';
        }

        if (biometricSetupBtn) {
            biometricSetupBtn.style.display = webAuthnAvailable ? 'inline-flex' : 'none';
        }

        if (biometricUnlockBtn) {
            biometricUnlockBtn.style.display = (webAuthnAvailable && hasPin && profile.biometricCredentialId) ? 'inline-flex' : 'none';
        }

        if (!hasPin) {
            applyAccessState(false);
            setPinMessage('Primero configura un PIN local para habilitar la bitácora offline.', 'info');
            return;
        }

        applyAccessState(isSessionUnlocked());
    }

    async function configurePin() {
        const pin = (pinNewInput && pinNewInput.value ? pinNewInput.value.trim() : '');
        const confirm = (pinConfirmInput && pinConfirmInput.value ? pinConfirmInput.value.trim() : '');

        if (!isPinFormatValid(pin)) {
            setPinMessage('El PIN debe tener entre 4 y 8 dígitos numéricos.', 'error');
            return;
        }

        if (pin !== confirm) {
            setPinMessage('El PIN y su confirmación no coinciden.', 'error');
            return;
        }

        const salt = generateSalt();
        const pinHash = await hashPin(pin, salt);
        const currentProfile = loadPinProfile() || {};

        savePinProfile({
            ...currentProfile,
            pinSalt: salt,
            pinHash: pinHash,
            updatedAt: new Date().toISOString(),
        });

        if (pinNewInput) pinNewInput.value = '';
        if (pinConfirmInput) pinConfirmInput.value = '';

        markSessionUnlocked(true);
        refreshAuthUi();
        setPinMessage('PIN guardado correctamente.', 'success');
        await showAlert('success', 'PIN guardado correctamente', 'Tu acceso local quedó activado en este dispositivo.');
    }

    async function unlockWithPin() {
        const profile = loadPinProfile();
        if (!profile) {
            setPinMessage('No existe PIN configurado. Debes crearlo primero.', 'error');
            return;
        }

        const pin = (pinInput && pinInput.value ? pinInput.value.trim() : '');
        if (!isPinFormatValid(pin)) {
            setPinMessage('Ingresa un PIN válido de 4 a 8 dígitos.', 'error');
            return;
        }

        const hash = await hashPin(pin, profile.pinSalt);
        if (hash !== profile.pinHash) {
            setPinMessage('PIN incorrecto.', 'error');
            await showAlert('error', 'PIN incorrecto', 'Verifica el PIN local e inténtalo de nuevo.');
            return;
        }

        if (pinInput) {
            pinInput.value = '';
        }
        markSessionUnlocked(true);
        refreshAuthUi();
        await showAlert('success', 'Bitácora desbloqueada', 'Ahora puedes registrar ingreso y salida.');
    }

    async function registerBiometricCredential() {
        if (!webAuthnAvailable) {
            setPinMessage('Este dispositivo no soporta desbloqueo biométrico WebAuthn.', 'error');
            return;
        }

        const profile = loadPinProfile();
        if (!profile) {
            setPinMessage('Configura primero el PIN antes de vincular huella.', 'error');
            return;
        }

        try {
            const userIdRaw = new TextEncoder().encode(pinIdentity || 'sigeth_user');
            const userId = userIdRaw.slice(0, 32);

            const credential = await navigator.credentials.create({
                publicKey: {
                    challenge: randomChallenge(),
                    rp: {
                        name: 'SIGETH Bitacora Offline'
                    },
                    user: {
                        id: userId,
                        name: pinIdentity,
                        displayName: config.employeeName || pinIdentity,
                    },
                    pubKeyCredParams: [
                        {type: 'public-key', alg: -7},
                        {type: 'public-key', alg: -257},
                    ],
                    authenticatorSelection: {
                        authenticatorAttachment: 'platform',
                        userVerification: 'required',
                        residentKey: 'preferred',
                    },
                    timeout: 60000,
                    attestation: 'none',
                }
            });

            const credentialId = toBase64Url(credential.rawId);
            savePinProfile({
                ...profile,
                biometricCredentialId: credentialId,
                biometricEnabledAt: new Date().toISOString(),
            });

            refreshAuthUi();
            setPinMessage('Huella vinculada correctamente para desbloqueo local.', 'success');
            await showAlert('success', 'Huella vinculada', 'Este dispositivo ya puede usar desbloqueo biométrico local.');
        } catch (error) {
            setPinMessage('No se pudo vincular huella en este dispositivo.', 'error');
            await showAlert('error', 'No se pudo vincular la huella', 'Intenta de nuevo o usa PIN local.');
        }
    }

    async function unlockWithBiometric() {
        if (!webAuthnAvailable) {
            setPinMessage('Este dispositivo no soporta WebAuthn.', 'error');
            return;
        }

        const profile = loadPinProfile();
        if (!profile || !profile.biometricCredentialId) {
            setPinMessage('No hay huella vinculada. Usa PIN o vincula huella.', 'error');
            return;
        }

        try {
            await navigator.credentials.get({
                publicKey: {
                    challenge: randomChallenge(),
                    allowCredentials: [
                        {
                            id: fromBase64Url(profile.biometricCredentialId),
                            type: 'public-key',
                        }
                    ],
                    userVerification: 'required',
                    timeout: 60000,
                }
            });

            markSessionUnlocked(true);
            refreshAuthUi();
            setPinMessage('Desbloqueo con huella exitoso.', 'success');
            await showAlert('success', 'Desbloqueo exitoso', 'La bitácora quedó desbloqueada con tu huella.');
        } catch (error) {
            setPinMessage('No se pudo validar huella. Intenta con PIN.', 'error');
            await showAlert('error', 'No se pudo validar la huella', 'Usa el PIN local para continuar.');
        }
    }

    function lockLocalSession() {
        markSessionUnlocked(false);
        refreshAuthUi();
    }

    function canUseActions() {
        if (!accessUnlocked) {
            setPinMessage('Bitácora bloqueada. Ingresa PIN o usa huella.', 'error');
            return false;
        }
        return true;
    }

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return '';
    }

    function formatLocalDateTime(date) {
        const pad = (value) => String(value).padStart(2, '0');
        const local = new Date(date.getTime() - (date.getTimezoneOffset() * 60000));
        return `${local.getFullYear()}-${pad(local.getMonth() + 1)}-${pad(local.getDate())}T${pad(local.getHours())}:${pad(local.getMinutes())}:${pad(local.getSeconds())}`;
    }

    function createUuid() {
        if (window.crypto && typeof window.crypto.randomUUID === 'function') {
            return window.crypto.randomUUID();
        }

        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (character) {
            const randomValue = Math.random() * 16 | 0;
            const value = character === 'x' ? randomValue : (randomValue & 0x3 | 0x8);
            return value.toString(16);
        });
    }

    function openDatabase() {
        if (databasePromise) {
            return databasePromise;
        }

        databasePromise = new Promise((resolve, reject) => {
            if (!('indexedDB' in window)) {
                reject(new Error('IndexedDB no está disponible en este navegador.'));
                return;
            }

            const request = window.indexedDB.open(dbName, dbVersion);

            request.onupgradeneeded = function (event) {
                const database = event.target.result;
                if (!database.objectStoreNames.contains(storeName)) {
                    const store = database.createObjectStore(storeName, {keyPath: 'offline_uuid'});
                    store.createIndex('sync_status', 'sync_status', {unique: false});
                    store.createIndex('captured_at', 'captured_at', {unique: false});
                }
            };

            request.onsuccess = function (event) {
                resolve(event.target.result);
            };

            request.onerror = function () {
                reject(new Error('No fue posible abrir la base local.'));
            };
        });

        return databasePromise;
    }

    async function getAllRecords() {
        const database = await openDatabase();
        return new Promise((resolve, reject) => {
            const transaction = database.transaction(storeName, 'readonly');
            const store = transaction.objectStore(storeName);
            const request = store.getAll();
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(new Error('No fue posible leer la cola local.'));
        });
    }

    async function upsertRecord(record) {
        const database = await openDatabase();
        return new Promise((resolve, reject) => {
            const transaction = database.transaction(storeName, 'readwrite');
            const store = transaction.objectStore(storeName);
            const request = store.put(record);
            request.onsuccess = () => resolve(record);
            request.onerror = () => reject(new Error('No fue posible guardar la marcación local.'));
        });
    }

    async function deleteRecord(offlineUuid) {
        const database = await openDatabase();
        return new Promise((resolve, reject) => {
            const transaction = database.transaction(storeName, 'readwrite');
            const store = transaction.objectStore(storeName);
            const request = store.delete(offlineUuid);
            request.onsuccess = () => resolve(true);
            request.onerror = () => reject(new Error('No fue posible limpiar la marcación sincronizada.'));
        });
    }

    async function updateRecord(offlineUuid, patch) {
        const database = await openDatabase();
        return new Promise((resolve, reject) => {
            const transaction = database.transaction(storeName, 'readwrite');
            const store = transaction.objectStore(storeName);
            const getRequest = store.get(offlineUuid);

            getRequest.onsuccess = () => {
                const currentRecord = getRequest.result;
                if (!currentRecord) {
                    resolve(null);
                    return;
                }
                const nextRecord = {...currentRecord, ...patch};
                store.put(nextRecord);
                resolve(nextRecord);
            };

            getRequest.onerror = () => reject(new Error('No fue posible actualizar la marcación local.'));
        });
    }

    function renderRecords(records) {
        if (!recordListNode) {
            return;
        }

        if (!records.length) {
            recordListNode.innerHTML = '<div class="record-item"><div><strong>No hay marcaciones guardadas</strong><div class="record-meta">Cuando presiones ingreso o salida, aparecerán aquí.</div></div><div class="record-badge synced">Lista</div></div>';
            return;
        }

        const sortedRecords = records.sort((left, right) => String(right.captured_at).localeCompare(String(left.captured_at)));
        recordListNode.innerHTML = sortedRecords.map((record) => {
            const badgeClass = record.sync_status === 'SYNCED' ? 'synced' : (record.sync_status === 'ERROR' ? 'error' : 'pending');
            const badgeLabel = record.sync_status === 'SYNCED' ? 'Sincronizado' : (record.sync_status === 'ERROR' ? 'Error' : 'Pendiente');
            const coords = `${record.latitude}, ${record.longitude}`;
            const errorText = record.sync_error ? `<div class="record-meta" style="color:#fecaca">${escapeHtml(record.sync_error)}</div>` : '';

            return `
                <div class="record-item">
                    <div>
                        <strong>${record.punch_type === 'EXIT' ? 'Salida' : 'Ingreso'} · ${escapeHtml(record.captured_at || '')}</strong>
                        <div class="record-meta">
                            GPS: ${escapeHtml(coords)}<br>
                            Precisión: ${escapeHtml(record.accuracy_m != null ? String(record.accuracy_m) : 'N/D')} m<br>
                            Origen: ${escapeHtml(record.source || 'PWA')}
                        </div>
                        ${errorText}
                    </div>
                    <div class="record-badge ${badgeClass}">${badgeLabel}</div>
                </div>
            `;
        }).join('');
    }

    function escapeHtml(text) {
        return String(text)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    async function refreshSummary() {
        const records = await getAllRecords();
        const pending = records.filter((record) => record.sync_status === 'PENDING');
        const synced = records.filter((record) => record.sync_status === 'SYNCED');
        if (pendingCountNode) {
            pendingCountNode.textContent = String(pending.length);
        }
        renderRecords(records);
        return {records, pending, synced};
    }

    function showGpsWarning(message) {
        if (!gpsWarningNode) {
            return;
        }
        gpsWarningNode.textContent = message;
        gpsWarningNode.hidden = false;
    }

    function hideGpsWarning() {
        if (gpsWarningNode) {
            gpsWarningNode.hidden = true;
        }
    }

    function getCurrentPosition() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('El navegador no soporta geolocalización.'));
                return;
            }

            navigator.geolocation.getCurrentPosition(
                resolve,
                reject,
                {
                    enableHighAccuracy: true,
                    timeout: 15000,
                    maximumAge: 0
                }
            );
        });
    }

    async function captureAttendance(punchType) {
        if (!canUseActions()) {
            return;
        }

        hideGpsWarning();
        setStatus('Solicitando GPS y capturando ubicación...', navigator.onLine ? 'online' : 'offline');

        try {
            const position = await getCurrentPosition();
            const now = new Date();
            const record = {
                offline_uuid: createUuid(),
                punch_type: punchType,
                captured_at: formatLocalDateTime(now),
                latitude: Number(position.coords.latitude.toFixed(6)),
                longitude: Number(position.coords.longitude.toFixed(6)),
                accuracy_m: position.coords.accuracy ? Number(position.coords.accuracy.toFixed(2)) : null,
                location_text: `GPS ${position.coords.latitude.toFixed(6)}, ${position.coords.longitude.toFixed(6)}`,
                sync_status: 'PENDING',
                synced_at: null,
                sync_error: '',
                source: 'PWA'
            };

            await upsertRecord(record);
            setStatus('Marcación guardada en el dispositivo. Se sincronizará cuando haya conexión.', navigator.onLine ? 'online' : 'offline');
            await refreshSummary();

            if (navigator.onLine) {
                await syncPendingRecords();
            }
        } catch (error) {
            if (error && (error.code === 1 || error.code === 2 || error.code === 3)) {
                showGpsWarning('Activa el GPS y concede permiso de ubicación para registrar la marcación.');
                setStatus('No se pudo obtener ubicación precisa. Vuelve a intentar con GPS activo.', 'offline');
                return;
            }

            showGpsWarning(error.message || 'No se pudo obtener la ubicación.');
            setStatus('No fue posible capturar la marcación.', 'offline');
        }
    }

    async function syncPendingRecords() {
        if (!canUseActions()) {
            return;
        }

        if (syncInProgress) {
            return;
        }

        if (!navigator.onLine) {
            setStatus('Sin conexión. La cola local seguirá guardando las marcaciones.', 'offline');
            return;
        }

        syncInProgress = true;
        setStatus('Sincronizando marcaciones pendientes...', 'online');

        try {
            const records = await getAllRecords();
            const pendingRecords = records.filter((record) => record.sync_status === 'PENDING');

            if (!pendingRecords.length) {
                setStatus('No hay marcaciones pendientes para sincronizar.', 'online');
                return;
            }

            const response = await fetch(config.syncUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({records: pendingRecords})
            });

            const data = await response.json();
            const syncedUuids = new Set((data.synced_uuids || []).map(String));
            const failedRecords = Array.isArray(data.failed_records) ? data.failed_records : [];
            const failedUuidMap = new Map(failedRecords.map((item) => [String(item.offline_uuid || ''), item.error || 'Error de sincronización']));

            for (const record of pendingRecords) {
                if (syncedUuids.has(String(record.offline_uuid))) {
                    await deleteRecord(record.offline_uuid);
                    continue;
                }

                if (failedUuidMap.has(String(record.offline_uuid))) {
                    await updateRecord(record.offline_uuid, {
                        sync_status: 'ERROR',
                        sync_error: failedUuidMap.get(String(record.offline_uuid))
                    });
                }
            }

            await refreshSummary();

            if (response.ok && data.status !== 'error') {
                setStatus(`Sincronización completada. Enviadas: ${data.created || 0} nuevas y ${data.updated || 0} actualizadas.`, 'online');
            } else {
                setStatus('La sincronización terminó con observaciones. Revisa la cola local.', 'offline');
            }
        } catch (error) {
            setStatus('No se pudo sincronizar en este momento. Los datos quedaron guardados localmente.', 'offline');
        } finally {
            syncInProgress = false;
        }
    }

    async function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            return;
        }

        try {
            await navigator.serviceWorker.register(config.swUrl, {scope: '/biometric/offline-attendance/'});
        } catch (error) {
            console.warn('No fue posible registrar el service worker', error);
        }
    }

    async function requestPersistentStorage() {
        if (!navigator.storage || typeof navigator.storage.persist !== 'function') {
            return;
        }

        try {
            await navigator.storage.persist();
        } catch (error) {
            console.warn('No fue posible solicitar almacenamiento persistente', error);
        }
    }

    function updateConnectionState() {
        if (navigator.onLine) {
            setStatus('Conexión detectada. La cola local se sincronizará automáticamente.', 'online');
        } else {
            setStatus('Sin conexión. Las marcaciones se guardarán en el dispositivo.', 'offline');
        }
    }

    async function bootstrap() {
        await requestPersistentStorage();
        await registerServiceWorker();
        if (isStandaloneMode) {
            appNode.classList.add('is-locked');
        }
        refreshAuthUi();
        updateConnectionState();
        await refreshSummary();

        if (navigator.onLine && accessUnlocked) {
            await syncPendingRecords();
        }
    }

    btnIncome && btnIncome.addEventListener('click', () => captureAttendance('INCOME'));
    btnExit && btnExit.addEventListener('click', () => captureAttendance('EXIT'));
    btnSync && btnSync.addEventListener('click', () => syncPendingRecords());
    pinSetBtn && pinSetBtn.addEventListener('click', () => {
        configurePin().catch(() => setPinMessage('No fue posible guardar el PIN.', 'error'));
    });
    pinUnlockBtn && pinUnlockBtn.addEventListener('click', () => {
        unlockWithPin().catch(() => setPinMessage('No fue posible validar el PIN.', 'error'));
    });
    pinResetBtn && pinResetBtn.addEventListener('click', lockLocalSession);
    biometricSetupBtn && biometricSetupBtn.addEventListener('click', () => {
        registerBiometricCredential().catch(() => setPinMessage('No fue posible vincular huella.', 'error'));
    });
    biometricUnlockBtn && biometricUnlockBtn.addEventListener('click', () => {
        unlockWithBiometric().catch(() => setPinMessage('No fue posible usar huella para desbloqueo.', 'error'));
    });
    pinInput && pinInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            unlockWithPin().catch(() => setPinMessage('No fue posible validar el PIN.', 'error'));
        }
    });

    window.addEventListener('online', () => {
        updateConnectionState();
        if (accessUnlocked) {
            syncPendingRecords();
        }
    });
    window.addEventListener('offline', updateConnectionState);

    bootstrap();
})();
