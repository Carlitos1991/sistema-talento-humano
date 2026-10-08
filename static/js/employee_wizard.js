/**
 * SIGETH - Employee Wizard Master Controller
 * Versión: 3.4 (Control Estricto de Visibilidad de Pestañas por Administrador)
 */

document.addEventListener('DOMContentLoaded', () => {
    initWizardTabs();
    initDetailPhotoUpload();
    initActionsLocalPagination();
});

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

window.getCookie = getCookie;

/**
 * 1. Control de Pestañas con Aplicación de Permisos del Administrador
 */
function initWizardTabs() {
    const navContainer = document.getElementById('wizardTabsNavigation');
    const wizardRoot = document.getElementById('employeeWizardContainer');
    if (!navContainer || !wizardRoot) return;

    const personId = wizardRoot.dataset.personId;
    const isDashboard = wizardRoot.dataset.isDashboard === 'true'; // True si es el portal del empleado propio
    let lastAuditedTab = '';

    // 1. Obtener el diccionario de visibilidades configurado por el Administrador
    let visibilities = {};
    const visibilitiesScript = document.getElementById('tab-visibilities-data');
    if (visibilitiesScript) {
        try {
            visibilities = JSON.parse(visibilitiesScript.textContent || '{}');
        } catch (e) {
            console.error('Error parseando tab_visibilities:', e);
        }
    } else if (wizardRoot.dataset.tabVisibilities) {
        try {
            visibilities = JSON.parse(wizardRoot.dataset.tabVisibilities);
        } catch (e) {
            console.error('Error parseando dataset tabVisibilities:', e);
        }
    }

    // 2. Aplicar restricciones de visibilidad a los botones y paneles
    const tabButtons = navContainer.querySelectorAll('.employee-detail-button');
    let firstVisibleTabId = null;

    tabButtons.forEach(btn => {
        const tabId = btn.dataset.tabTarget;
        const miniCheck = btn.querySelector('.mini-check');

        // Determinar si está permitida (en visibilities los valores vienen como boolean o string "true"/"false")
        const isAllowed = visibilities[tabId] === true || visibilities[tabId] === 'true';

        // Actualizar el estado visual del mini-check si existe (para vista admin)
        if (miniCheck) {
            miniCheck.classList.toggle('visible', isAllowed);
            miniCheck.innerHTML = isAllowed ? '<i class="fa-solid fa-check"></i>' : '';
        }

        // SI ES EL DASHBOARD DEL EMPLEADO (o usuario sin permiso de editar):
        // Si el administrador deshabilitó la pestaña, se oculta completamente el botón
        if (isDashboard) {
            if (!isAllowed) {
                btn.style.setProperty('display', 'none', 'important');
                const pane = document.getElementById(`tab-pane-${tabId}`);
                if (pane) pane.style.setProperty('display', 'none', 'important');
            } else {
                btn.style.display = '';
                if (!firstVisibleTabId) {
                    firstVisibleTabId = tabId;
                }
            }
        } else {
            // En vista administrativa siempre se ven los botones para poder gestionarlos
            if (!firstVisibleTabId) {
                firstVisibleTabId = tabId;
            }
        }
    });

    // 3. Determinar pestaña inicial asegurando que sea una permitida
    const savedPersonId = localStorage.getItem('wizardPersonId');
    let activeTabId = firstVisibleTabId || 'personal';

    const navEntries = window.performance?.getEntriesByType?.("navigation");
    const isReload = navEntries && navEntries.length > 0 && navEntries[0].type === "reload";

    if (savedPersonId === personId && isReload) {
        const candidateTab = localStorage.getItem('wizardActiveTab');
        // Validar que la pestaña en caché esté permitida
        if (candidateTab && (!isDashboard || visibilities[candidateTab] === true || visibilities[candidateTab] === 'true')) {
            activeTabId = candidateTab;
        }
    } else {
        localStorage.setItem('wizardPersonId', personId || '');
        localStorage.setItem('wizardActiveTab', activeTabId);
    }

    // Activar pestaña inicial permitida
    if (activeTabId) {
        switchTab(activeTabId, false);
    }

    // 4. Click delegado en los botones de pestañas
    navContainer.addEventListener('click', (e) => {
        const miniCheck = e.target.closest('.mini-check');
        if (miniCheck) {
            e.stopPropagation();
            handleTabVisibilityToggle(miniCheck);
            return;
        }

        const btn = e.target.closest('.employee-detail-button');
        if (!btn) return;

        const targetTab = btn.dataset.tabTarget;
        if (!targetTab) return;

        // Bloqueo de seguridad: no permitir activar si no está visible en el dashboard
        if (isDashboard && visibilities[targetTab] !== true && visibilities[targetTab] !== 'true') {
            return;
        }

        switchTab(targetTab, true);
    });

    function switchTab(tabId, shouldAudit = true) {
        const targetBtn = navContainer.querySelector(`[data-tab-target="${tabId}"]`);
        const targetPane = document.getElementById(`tab-pane-${tabId}`);

        if (!targetBtn || !targetPane) return;

        navContainer.querySelectorAll('.employee-detail-button').forEach(b => b.classList.remove('active'));
        targetBtn.classList.add('active');

        document.querySelectorAll('.wizard-tab-pane').forEach(p => {
            p.classList.remove('active');
        });
        targetPane.classList.add('active');

        localStorage.setItem('wizardActiveTab', tabId);

        if (shouldAudit) {
            const label = targetBtn.querySelector('.employee-detail-button-label')?.textContent?.trim() || tabId;
            if (label !== lastAuditedTab) {
                lastAuditedTab = label;
                auditTabAccess(personId, tabId, label);
            }
        }

        if (tabId === 'actions') {
            initActionsLocalPagination();
        }

        window.dispatchEvent(new Event('resize'));
    }
}

/**
 * 2. Auditoría de Pestañas
 */
function auditTabAccess(personId, tabId, tabName) {
    if (!personId) return;
    const csrf = getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    fetch(`/employee/person/${personId}/audit/tab/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrf
        },
        body: JSON.stringify({
            tab_id: tabId,
            tab_name: tabName
        })
    }).catch(err => console.error('Error auditoría tab:', err));
}

/**
 * 3. Mini-Check de Visibilidad (Configuración del Administrador)
 */
async function handleTabVisibilityToggle(checkElement) {
    const btn = checkElement.closest('.employee-detail-button');
    const tabName = btn.querySelector('.employee-detail-button-label')?.textContent?.trim() || 'esta pestaña';
    const isCurrentlyVisible = checkElement.classList.contains('visible');
    const actionText = isCurrentlyVisible ? 'deshabilitar' : 'habilitar';

    const {value: selection} = await Swal.fire({
        title: `¿Cómo desea ${actionText} la pestaña "${tabName}"?`,
        icon: 'question',
        showDenyButton: true,
        showCancelButton: true,
        confirmButtonText: '<i class="fa-solid fa-user me-1"></i> SOLO PARA ESTE EMPLEADO',
        denyButtonText: '<i class="fa-solid fa-users me-1"></i> PARA TODOS LOS EMPLEADOS',
        cancelButtonText: 'CANCELAR',
        buttonsStyling: false,
        customClass: {
            actions: 'swal2-actions-vertical gap-2 w-100 px-4',
            confirmButton: 'btn-dark-blue-rectangle w-100 py-2',
            denyButton: 'btn-green-rectangle w-100 py-2',
            cancelButton: 'btn-dark-blue-rectangle-outline w-100 py-2'
        }
    });

    const wizardRoot = document.getElementById('employeeWizardContainer');
    const personId = wizardRoot ? wizardRoot.dataset.personId : null;
    const tabId = btn.dataset.tabTarget;

    if (selection === true) {
        // Lógica individual
        try {
            const res = await fetch('/employee/api/profile-visibility/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    person_id: personId,
                    user_id: personId,
                    tab_id: tabId,
                    is_visible: !isCurrentlyVisible
                })
            });
            const data = await res.json();
            if (data.success) {
                checkElement.classList.toggle('visible', !isCurrentlyVisible);
                checkElement.innerHTML = !isCurrentlyVisible ? '<i class="fa-solid fa-check"></i>' : '';
                Swal.fire({
                    icon: 'success',
                    title: '¡Actualizado!',
                    text: `Pestaña actualizada para este empleado.`,
                    timer: 1500,
                    showConfirmButton: false
                });
            } else {
                Swal.fire('Atención', data.message || 'No se pudo actualizar.', 'warning');
            }
        } catch (e) {
            Swal.fire('Error', 'Problema de conexión con el servidor', 'error');
        }
    } else if (selection === false) {
        // Lógica masiva
        try {
            const formData = new FormData();
            formData.append('tab_id', tabId);
            formData.append('is_visible', (!isCurrentlyVisible).toString());

            const res = await fetch('/employee/api/bulk-visibility/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                checkElement.classList.toggle('visible', !isCurrentlyVisible);
                checkElement.innerHTML = !isCurrentlyVisible ? '<i class="fa-solid fa-check"></i>' : '';
                Swal.fire({
                    icon: 'success',
                    title: '¡Éxito Masivo!',
                    text: `Se ha ${!isCurrentlyVisible ? 'habilitado' : 'deshabilitado'} para todos los empleados.`,
                    timer: 1500,
                    showConfirmButton: false
                });
            } else {
                Swal.fire('Atención', data.message || 'Error en acción masiva.', 'warning');
            }
        } catch (e) {
            Swal.fire('Error', 'No se pudo realizar la acción masiva', 'error');
        }
    }
}

/**
 * 4. Paginación Local para Acciones de Personal
 */
function initActionsLocalPagination() {
    const $container = $('[data-action-history-table]');
    if (!$container.length) return;

    const rowsPerPage = 10;
    let currentPage = 1;
    let searchQuery = ($('#action-search-input').val() || '').toLowerCase();
    const $allRows = $container.find('[data-action-row]');

    const updateTable = () => {
        const $filteredRows = $allRows.filter(function () {
            if (!searchQuery) return true;
            return $(this).text().toLowerCase().includes(searchQuery);
        });

        const totalRows = $filteredRows.length;
        const totalPages = Math.max(1, Math.ceil(totalRows / rowsPerPage));

        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;

        const start = (currentPage - 1) * rowsPerPage;
        const end = start + rowsPerPage;

        $allRows.hide();
        $filteredRows.slice(start, end).show();

        const emptyRow = $('[data-action-empty-row]');
        if (totalRows === 0) {
            if (emptyRow.length === 0) {
                $('[data-action-tbody]').append(`
                    <tr data-action-empty-row>
                        <td colspan="6" class="text-center py-5">
                            <i class="fas fa-inbox fa-2x text-muted mb-2"></i>
                            <p class="text-muted mb-0">No hay acciones para la búsqueda.</p>
                        </td>
                    </tr>
                `);
            } else {
                emptyRow.show();
            }
            $('[data-action-page-info]').text(`Mostrando 0-0 de 0`);
            $('[data-action-total-pages]').text(`de 1`);
            $('[data-action-page-input]').val(1);
            $('[data-action-prev], [data-action-first], [data-action-next], [data-action-last]').prop('disabled', true);
        } else {
            if (emptyRow.length) emptyRow.hide();
            $('[data-action-page-info]').text(`Mostrando ${start + 1}-${Math.min(end, totalRows)} de ${totalRows}`);
            $('[data-action-total-pages]').text(`de ${totalPages}`);
            $('[data-action-page-input]').val(currentPage);
            $('[data-action-prev], [data-action-first]').prop('disabled', currentPage === 1);
            $('[data-action-next], [data-action-last]').prop('disabled', currentPage === totalPages);
        }
    };

    $('[data-action-next]').off('click').on('click', () => {
        currentPage++;
        updateTable();
    });
    $('[data-action-prev]').off('click').on('click', () => {
        currentPage--;
        updateTable();
    });
    $('[data-action-first]').off('click').on('click', () => {
        currentPage = 1;
        updateTable();
    });
    $('[data-action-last]').off('click').on('click', () => {
        currentPage = 99999;
        updateTable();
    });

    $('[data-action-page-input]').off('change').on('change', function () {
        let val = parseInt($(this).val(), 10);
        if (!isNaN(val)) {
            currentPage = val;
            updateTable();
        }
    });

    $('#action-search-input').off('input').on('input', function () {
        searchQuery = $(this).val().toLowerCase();
        currentPage = 1;
        updateTable();
    });

    $('#action-clear-btn').off('click').on('click', function () {
        $('#action-search-input').val('');
        searchQuery = '';
        currentPage = 1;
        updateTable();
    });

    updateTable();
}

/**
 * 5. Foto de Perfil
 */
function initDetailPhotoUpload() {
    const photoInput = document.getElementById('detailPhotoInput');
    const photoForm = document.getElementById('detailPhotoForm');
    const btnSave = document.getElementById('btnSaveDetailPhoto');
    const imgPreview = document.getElementById('detailAvatarImg');
    const placeholder = document.getElementById('detailAvatarPlaceholder');

    if (!photoInput || !photoForm) return;

    photoInput.addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
                if (imgPreview) {
                    imgPreview.src = event.target.result;
                    imgPreview.classList.remove('hidden');
                }
                if (placeholder) {
                    placeholder.classList.add('hidden');
                }
                if (btnSave) {
                    btnSave.classList.remove('hidden');
                }
            };
            reader.readAsDataURL(file);
        }
    });

    photoForm.addEventListener('submit', (e) => {
        e.preventDefault();
        if (window.submitAjaxForm) {
            window.submitAjaxForm(e, () => {
                if (btnSave) btnSave.classList.add('hidden');
            });
        } else {
            photoForm.submit();
        }
    });
}

// Delegación global para modales de detalle de acciones de personal
$(document).on('click', '.js-close-detail-modal', function () {
    $('#action-modal-employee').empty();
    $('body, html').removeClass('modal-open no-scroll');
});

$(document).on('click', '#action-modal-employee .modal-overlay', function (e) {
    if (e.target === this) {
        $('#action-modal-employee').empty();
        $('body, html').removeClass('modal-open no-scroll');
    }
});

$(document).off('click', '.js-view-action-detail').on('click', '.js-view-action-detail', function (e) {
    e.preventDefault();
    const url = $(this).data('url');
    const modalPlaceholder = $('#action-modal-employee');

    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(async response => {
            const contentType = (response.headers.get('content-type') || '').toLowerCase();
            const body = await response.text();

            if (!response.ok) {
                console.error('Respuesta completa del detalle:', {
                    url: response.url,
                    status: response.status,
                    statusText: response.statusText,
                    body
                });
                const responsePreview = body.replace(/\s+/g, ' ').trim().slice(0, 500);
                throw new Error(
                    `HTTP ${response.status} ${response.statusText} en ${response.url}. ` +
                    `Respuesta: ${responsePreview || '(vacía)'}`
                );
            }

            if (contentType.includes('application/json')) {
                try {
                    return JSON.parse(body);
                } catch (error) {
                    throw new Error(`JSON inválido (${response.status}) en ${response.url}`);
                }
            }

            return body;
        })
        .then(payload => {
            const html = typeof payload === 'string' ? payload : payload && payload.html;
            if (typeof html === 'string' && html.trim()) {
                modalPlaceholder.html(html);
                modalPlaceholder.find('.modal-overlay').first()
                    .removeClass('hidden')
                    .css('display', 'flex');
                $('body').addClass('modal-open');
            } else {
                Swal.fire("Error", "Respuesta inválida del servidor.", "error");
            }
        })
        .catch(err => {
            console.error('Error al cargar el detalle de la acción:', err);
            Swal.fire({
                icon: 'error',
                title: 'Error al cargar detalle',
                html: `<pre style="white-space: pre-wrap; text-align: left; max-height: 260px; overflow: auto;">${String(err.message || 'Error desconocido').replace(/[<>&]/g, character => ({'<': '&lt;', '>': '&gt;', '&': '&amp;'}[character]))}</pre>`,
                width: 700
            });
        });
});
/**
 * Callback tras actualizar los datos desde el modal de edición
 */
window.onPersonUpdatedSuccess = function (data) {
    if (!data) return;

    // 1. Reemplazar el contenido completo de la pestaña de Datos Personales
    const tabPersonal = document.getElementById('tab-pane-personal');
    if (tabPersonal && data.tab_html) {
        tabPersonal.innerHTML = data.tab_html;

        // Re-inicializar el listener del input/form de foto de la pestaña recién inyectada
        if (typeof initDetailPhotoUpload === 'function') {
            initDetailPhotoUpload();
        }
    }

    // 2. Actualizar el Banner Institucional superior (Nombre y Cédula)
    const bannerTitle = document.querySelector('.banner-info-employee-detail h1');
    if (bannerTitle && data.full_name) {
        bannerTitle.textContent = data.full_name;
    }

    const bannerBadges = document.querySelectorAll('.banner-badges-group .banner-badge-info');
    if (bannerBadges.length > 0 && data.document_number) {
        bannerBadges[0].innerHTML = `<i class="fa-solid fa-id-card me-1"></i> ${data.document_number}`;
    }
};