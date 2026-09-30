/**
 * SIGETH - Employee Wizard Master Controller
 * Versión: 3.0 (Vanilla JS Puro - 100% Sin Vue.js)
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
 * 1. Control de Pestañas con Vanilla JS
 */
function initWizardTabs() {
    const navContainer = document.getElementById('wizardTabsNavigation');
    const wizardRoot = document.getElementById('employeeWizardContainer');
    if (!navContainer || !wizardRoot) return;

    const personId = wizardRoot.dataset.personId;
    let lastAuditedTab = 'Datos Personales';

    // Recuperar pestaña guardada
    const savedPersonId = localStorage.getItem('wizardPersonId');
    let activeTabId = 'personal';

    let isReload = false;
    const navEntries = window.performance?.getEntriesByType?.("navigation");
    if (navEntries && navEntries.length > 0) {
        isReload = navEntries[0].type === "reload";
    }

    if (savedPersonId === personId && isReload) {
        activeTabId = localStorage.getItem('wizardActiveTab') || 'personal';
    } else {
        localStorage.setItem('wizardPersonId', personId || '');
        localStorage.setItem('wizardActiveTab', 'personal');
    }

    // Activar pestaña inicial
    switchTab(activeTabId, false);

    // Click delegado en los botones de pestañas
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

        switchTab(targetTab, true);
    });

    function switchTab(tabId, shouldAudit = true) {
        const targetBtn = navContainer.querySelector(`[data-tab-target="${tabId}"]`);
        const targetPane = document.getElementById(`tab-pane-${tabId}`);

        if (!targetBtn || !targetPane) return;

        // 1. Botón activo en navegación
        navContainer.querySelectorAll('.employee-detail-button').forEach(b => b.classList.remove('active'));
        targetBtn.classList.add('active');

        // 2. Panel visible (display block) y ocultar los demás
        document.querySelectorAll('.wizard-tab-pane').forEach(p => {
            p.classList.remove('active');
        });
        targetPane.classList.add('active');

        localStorage.setItem('wizardActiveTab', tabId);

        // 3. Auditoría
        if (shouldAudit) {
            const label = targetBtn.querySelector('.employee-detail-button-label')?.textContent?.trim();
            if (label && label !== lastAuditedTab) {
                lastAuditedTab = label;
                auditTabAccess(personId, label);
            }
        }

        // 4. Si es la pestaña de acciones o teletrabajo, refrescar
        if (tabId === 'actions') {
            initActionsLocalPagination();
        }

        window.dispatchEvent(new Event('resize'));
    }
}

/**
 * 2. Auditoría de Pestañas
 */
function auditTabAccess(personId, tabName) {
    if (!personId) return;
    const csrf = getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';

    fetch(`/employee/person/${personId}/audit/tab/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-CSRFToken': csrf
        },
        body: JSON.stringify({tab_name: tabName})
    }).catch(err => console.error('Error auditoría tab:', err));
}

/**
 * 3. Mini-Check de Visibilidad
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
        confirmButtonText: 'Solo para este empleado',
        denyButtonText: 'Para TODOS los empleados',
        cancelButtonText: 'Cancelar',
        buttonsStyling: false,
        customClass: {
            confirmButton: 'btn-dark-blue-rectangle me-2',
            denyButton: 'btn-green-rectangle me-2',
            cancelButton: 'btn-dark-blue-rectangle-outline'
        }
    });

    const wizardRoot = document.getElementById('employeeWizardContainer');
    const personId = wizardRoot ? wizardRoot.dataset.personId : null;
    const tabId = btn.dataset.tabTarget;

    if (selection === true) {
        try {
            const res = await fetch('/employee/api/profile-visibility/', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken')},
                body: JSON.stringify({user_id: personId, tab_id: tabId, is_visible: !isCurrentlyVisible})
            });
            const data = await res.json();
            if (data.success) {
                checkElement.classList.toggle('visible', !isCurrentlyVisible);
                checkElement.innerHTML = !isCurrentlyVisible ? '<i class="fa-solid fa-check"></i>' : '';
                if (window.Toast) window.Toast.fire({icon: 'success', title: 'Actualizado para este usuario'});
            }
        } catch (e) {
            Swal.fire('Error', 'Problema de conexión', 'error');
        }
    } else if (selection === false) {
        try {
            const formData = new FormData();
            formData.append('tab_id', tabId);
            formData.append('is_visible', !isCurrentlyVisible);

            const res = await fetch('/employee/api/bulk-visibility/', {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken')},
                body: formData
            });
            const data = await res.json();
            if (data.success) {
                checkElement.classList.toggle('visible', !isCurrentlyVisible);
                checkElement.innerHTML = !isCurrentlyVisible ? '<i class="fa-solid fa-check"></i>' : '';
                Swal.fire('¡Éxito Masivo!', `Se ha ${!isCurrentlyVisible ? 'habilitado' : 'deshabilitado'} para todos los empleados.`, 'success');
            }
        } catch (e) {
            Swal.fire('Error', 'No se pudo realizar la acción masiva', 'error');
        }
    }
}

/**
 * 4. Paginación Local para Acciones
 */
function initActionsLocalPagination() {
    const $allRows = $('[data-action-row]');
    if (!$allRows.length) return;

    const rowsPerPage = 10;
    let currentPage = 1;
    let searchQuery = ($('#action-search-input').val() || '').toLowerCase();

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
        let val = parseInt($(this).val());
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
    $('body').removeClass('modal-open');
});

$(document).off('click', '.js-view-action-detail').on('click', '.js-view-action-detail', function (e) {
    e.preventDefault();
    const url = $(this).data('url');
    const modalPlaceholder = $('#action-modal-employee');

    fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(response => response.json())
        .then(data => {
            if (data && data.html) {
                modalPlaceholder.html(`
                    <div class="modal-overlay" style="display:flex;">
                        <div class="modal-container-medium animate-scale-in" 
                             style="max-width:850px;background:#fff;border-radius:12px;display:flex;flex-direction:column;max-height:85vh;overflow:hidden;box-shadow:0 25px 50px -12px rgba(0,0,0,.25);">
                            ${data.html}
                        </div>
                    </div>
                `);
                $('body').addClass('modal-open');
            } else {
                Swal.fire("Error", "Respuesta inválida del servidor.", "error");
            }
        })
        .catch(err => Swal.fire("Error", "No se pudo cargar el detalle.", "error"));
});