/* JS para cargar y controlar el modal usando las clases globales de style.css */

function openPayslipDetail(url) {
    // 1. Buscamos el HTML en el servidor (solicitud AJAX para obtener solo el partial)
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(response => response.text())
        .then(html => {
            // 2. Inyectamos el HTML en el contenedor. Buscamos ids alternativos
            let container = document.getElementById('modal-container') || document.getElementById('modal-root');
            // Si no existe, lo creamos dinámicamente para evitar errores de null
            if (!container) {
                container = document.createElement('div');
                // preferimos el id 'modal-root' usado por otras partes del sistema
                container.id = 'modal-root';
                document.body.appendChild(container);
            }
            container.innerHTML = html;

            // 3. Mostramos el modal quitando la clase 'hidden' global
            const backdrop = document.getElementById('payslipBackdrop');
            if (backdrop) {
                backdrop.classList.remove('hidden');
                document.body.classList.add('modal-open'); // Clase global para evitar scroll

                // 4. Activamos los botones
                initModalEvents(backdrop);
            }
        })
        .catch(error => console.error('Error cargando el modal del rol:', error));
}

function closeDetailModal() {
    const backdrop = document.getElementById('payslipBackdrop');
    if (backdrop) {
        // Volvemos a agregar la clase 'hidden' para ocultarlo
        backdrop.classList.add('hidden');
        document.body.classList.remove('modal-open');

        // Limpiamos el HTML para no dejar basura en el DOM
        setTimeout(() => {
            const container = document.getElementById('modal-container') || document.getElementById('modal-root');
            if (container) container.innerHTML = '';
            // Después de cerrar el modal, refrescamos la tabla de roles para reflejar cambios
            try { refreshPayslipTable(); } catch (e) { console.debug('refreshPayslipTable error', e); }
        }, 300);
    }
}

// Refresca el partial de la tabla de roles (usa la URL base en la plantilla)
function refreshPayslipTable() {
    const periodId = window.CURRENT_PERIOD_ID || '';
    if (!periodId || !window.URLS || !window.URLS.baseList) return;
    // Preserve/merge existing URL params with saved session values so we don't wipe user's filters when refreshing
    try{
        const params = new URLSearchParams(window.location.search || '');
        // Ensure period_id is present/overridden
        params.set('period_id', periodId);

        // If q/page not present in URL, try sessionStorage (support both reserve_funds and payslip keys)
        if (!params.has('q')) {
            const q = sessionStorage.getItem('reserve_funds_q') || sessionStorage.getItem('payslip_q') || '';
            if (q) params.set('q', q);
        }
        if (!params.has('page')) {
            const p = sessionStorage.getItem('reserve_funds_page') || sessionStorage.getItem('payslip_page') || '';
            if (p) params.set('page', p);
        }

        const url = window.URLS.baseList + '?' + params.toString();
        fetch(url, { headers: {'X-Requested-With': 'XMLHttpRequest'} })
            .then(res => res.json())
            .then(data => {
                if (data && data.html) {
                    const container = document.getElementById('payslip-table-container');
                    if (container) container.innerHTML = data.html;
                }
            })
            .catch(err => console.debug('Error refrescando tabla de roles:', err));
        return;
    }catch(e){
        // fallback to simple URL if anything fails
    }
    const url = window.URLS.baseList + `?period_id=${periodId}`;
    fetch(url, { headers: {'X-Requested-With': 'XMLHttpRequest'} })
        .then(res => res.json())
        .then(data => {
            if (data && data.html) {
                const container = document.getElementById('payslip-table-container');
                if (container) container.innerHTML = data.html;
            }
        })
        .catch(err => console.debug('Error refrescando tabla de roles:', err));
}

function initModalEvents(backdrop) {
    // Cerrar al hacer clic fuera del contenedor blanco (en el overlay oscuro)
    backdrop.addEventListener('click', function (ev) {
        if (ev.target === backdrop) {
            // Si hay inputs en modo edición, guardarlos antes de cerrar
            const editingInputs = Array.from(backdrop.querySelectorAll('.val-input.editing'));
            if (editingInputs && editingInputs.length) {
                // Guardar todos y luego cerrar modal
                const saves = editingInputs.map(inp => saveInputValue(inp));
                Promise.all(saves).then(() => closeDetailModal()).catch(() => closeDetailModal());
            } else {
                closeDetailModal();
            }
        }
    });

    // Delegación para botones de acción (Cerrar e Imprimir)
    const closeBtns = backdrop.querySelectorAll('[data-action="close"]');
    closeBtns.forEach(btn => btn.addEventListener('click', closeDetailModal));

    const printBtn = backdrop.querySelector('[data-action="print"]');
    if (printBtn) {
        printBtn.addEventListener('click', () => {
            try {
                const modalContainer = backdrop.querySelector('.modal-container-medium');
                if (!modalContainer) return;

                // Crear/inyectar nota y total en letras dentro del modal (si no existen)
                const existingNote = modalContainer.querySelector('.print-note');
                const existingTotalWords = modalContainer.querySelector('.print-total-words');

                function numberToWordsES(n) {
                    const units = ['','uno','dos','tres','cuatro','cinco','seis','siete','ocho','nueve','diez','once','doce','trece','catorce','quince','dieciseis','diecisiete','dieciocho','diecinueve'];
                    const tens = ['','','veinte','treinta','cuarenta','cincuenta','sesenta','setenta','ochenta','noventa'];
                    const hundreds = ['','ciento','doscientos','trescientos','cuatrocientos','quinientos','seiscientos','setecientos','ochocientos','novecientos'];
                    if (n === 0) return 'cero';
                    if (n < 20) return units[n];
                    if (n < 100) {
                        if (n < 30 && n >= 20) return (n===20)?'veinte':'veinti'+units[n-20];
                        const u = n%10; return tens[Math.floor(n/10)] + (u? ' y ' + units[u] : '');
                    }
                    if (n < 1000) {
                        if (n === 100) return 'cien';
                        return hundreds[Math.floor(n/100)] + (n%100? ' ' + numberToWordsES(n%100): '');
                    }
                    if (n < 1000000) {
                        const miles = Math.floor(n/1000);
                        const rest = n%1000;
                        const milesText = (miles === 1)? 'mil' : numberToWordsES(miles) + ' mil';
                        return milesText + (rest? ' ' + numberToWordsES(rest): '');
                    }
                    const millones = Math.floor(n/1000000);
                    const resto = n%1000000;
                    const millonesText = (millones === 1)? 'un millon' : numberToWordsES(millones) + ' millones';
                    return millonesText + (resto? ' ' + numberToWordsES(resto): '');
                }

                if (!existingTotalWords) {
                    const netEl = modalContainer.querySelector('#liquido-pagar') || document.getElementById('liquido-pagar');
                    if (netEl) {
                        const raw = netEl.innerText || netEl.textContent || '';
                        const num = parseFloat((raw+'').replace(/[^0-9.,-]/g,'').replace(/,/g, '.')) || 0;
                        const integer = Math.floor(Math.abs(num));
                        const cents = Math.round((Math.abs(num) - integer) * 100);
                        const wordsInt = numberToWordsES(integer).toUpperCase();
                        const wordsCents = (cents>0)? numberToWordsES(cents).toUpperCase() : 'CERO';
                        const netWordsEl = document.createElement('div');
                        netWordsEl.className = 'print-total-words';
                        netWordsEl.innerText = `LIQUIDO A RECIBIR: ${wordsInt} DÓLARES CON ${wordsCents} CENTAVOS`;
                        modalContainer.insertBefore(netWordsEl, modalContainer.firstChild);
                    }
                }

                if (!existingNote) {
                    const note = document.createElement('div');
                    note.className = 'print-note';
                    note.innerText = 'ESTE DOCUMENTO TIENE VALIDEZ LEGAL AL ESTAR SELLADO POR LA DIRECCIÓN DE RECURSOS HUMANOS';
                    modalContainer.appendChild(note);
                }

                // Imprimir lo que se ve en pantalla (modal)
                window.print();

                // Limpiar elementos añadidos
                setTimeout(() => {
                    const addedNote = modalContainer.querySelectorAll('.print-note');
                    const addedWords = modalContainer.querySelectorAll('.print-total-words');
                    if (!existingNote) addedNote.forEach(n => n.parentNode && n.parentNode.removeChild(n));
                    if (!existingTotalWords) addedWords.forEach(n => n.parentNode && n.parentNode.removeChild(n));
                }, 500);
            } catch (err) {
                console.error('Error al preparar impresión (fallback):', err);
                window.print();
            }
        });
    }
}

// Cerrar con la tecla Escape
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeDetailModal();
});

// Exponer globalmente
window.openPayslipDetail = openPayslipDetail;

// Helper: sanear un id (quitar puntos/comas u otros) para usar en URLs
function sanitizeId(raw) {
    if (typeof raw === 'undefined' || raw === null) return '';
    return String(raw).toString().replace(/[^0-9]/g, '');
}

// Helper: guardar el valor de un input .val-input y actualizar UI; retorna Promise
function saveInputValue(input) {
    return new Promise((resolve, reject) => {
        if (!input) return resolve({ok:false, msg:'no input'});
        const rawVal = (input.value||'').trim();
        // Marcar como guardando para prevenir dobles envíos
        try { input.dataset.saving = '1'; input.disabled = true; } catch(e){}

        // Normalizar entradas: aceptar separador decimal ',' y distintos formatos de miles
        function normalizeNumberString(str) {
            if (!str) return '';
            // eliminar espacios y símbolos de moneda
            let s = String(str).trim();
            s = s.replace(/[^0-9.,-]/g, '');
            // Si contiene tanto '.' como ',' asumimos que '.' es separador de miles y ',' decimal
            if (s.indexOf('.') !== -1 && s.indexOf(',') !== -1) {
                s = s.replace(/\./g, ''); // quitar separadores de miles
                s = s.replace(/,/g, '.'); // convertir decimal
            } else if (s.indexOf(',') !== -1 && s.indexOf('.') === -1) {
                // sólo coma: convertir a punto
                s = s.replace(/,/g, '.');
            }
            // ahora s debe ser un número con '.' como decimal
            return s;
        }
        const itemIdRaw = input.dataset.itemId;
        const itemId = sanitizeId(itemIdRaw);
        const cleaned = normalizeNumberString(rawVal);
        const parsed = parseFloat(cleaned);
        if (cleaned === '' || isNaN(parsed) || !itemId) {
            return resolve({ok:false, msg:'invalid'});
        }
        const formData = new FormData();
        formData.append('new_value', parsed.toFixed(2));
        const csrfToken = getCookie('csrftoken');
        fetch(`/payroll/payslip-item/${itemId}/update/`, {
            method: 'POST', headers: {'X-CSRFToken': csrfToken, 'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'}, body: formData
        })
        .then(res => {
            // intentar parsear JSON, si viene HTML devolver error
            return res.text().then(text => {
                try { return JSON.parse(text); } catch (e) { throw new Error('invalid-json'); }
            });
        })
        .then(data => {
                if (data && data.success) {
                const span = input.parentElement.querySelector(`.val[data-item-id="${itemIdRaw}"]`);
                if (span) {
                    span.innerText = `$ ${parseFloat(parsed).toFixed(2)}`;
                    span.style.display = 'inline-block';
                    span.classList.add('seal-animate');
                    setTimeout(()=>span.classList.remove('seal-animate'), 600);
                }
                if (document.getElementById('total-ingresos'))
                    document.getElementById('total-ingresos').innerText = `$ ${parseFloat(data.new_total_income).toFixed(2)}`;
                if (document.getElementById('total-egresos'))
                    document.getElementById('total-egresos').innerText = `$ ${parseFloat(data.new_total_deduction).toFixed(2)}`;
                if (document.getElementById('liquido-pagar'))
                    document.getElementById('liquido-pagar').innerText = `$ ${parseFloat(data.new_net_pay).toFixed(2)}`;
                // actualizar input con valor formateado y marcar original
                input.value = parseFloat(parsed).toFixed(2);
                input.dataset.original = input.value;
                input.style.display = 'none';
                input.classList.remove('editing');
                try { delete input.dataset.saving; input.disabled = false; } catch(e){}
                // No mostrar notificación; actualizamos totales en el modal y dejaremos
                // que el cierre del modal refresque la lista principal.
                resolve({ok:true, data});
            } else {
                try { delete input.dataset.saving; input.disabled = false; } catch(e){}
                resolve({ok:false, data});
            }
        })
        .catch(err => {
            console.error('Error al guardar item:', err);
            try { delete input.dataset.saving; input.disabled = false; } catch(e){}
            if (typeof Swal !== 'undefined') Swal.fire({icon:'error', title:'Error', text:'Error de conexión.'});
            resolve({ok:false, err});
        });
    });
}

/* =====================================================================
   LÓGICA PARA MODIFICAR RUBROS Y RETENER PAGOS
   ===================================================================== */

// Manejo de edición inline: click en el span con clase .val.sealed lo convierte en input
document.addEventListener('click', function (e) {
    const span = e.target.closest('.val.sealed');
    if (span) {
        const id = span.dataset.itemId;
        const input = span.parentElement.querySelector(`.val-input[data-item-id="${id}"]`);
        if (!input) return;
        // Guardar original para poder cancelar si el usuario hace clic fuera
        input.dataset.original = input.value;
        // Mostrar input y ocultar span
        span.style.display = 'none';
        input.style.display = 'inline-block';
        input.classList.add('editing');
        setTimeout(() => { input.focus(); input.select(); }, 20);
    }
});

// Guardar con Enter en el input, cancelar con Escape
document.addEventListener('keydown', function (e) {
    const target = e.target;
    if (!target || !target.classList) return;
    if (target.classList.contains('val-input')) {
        if (e.key === 'Escape') {
            // cancelar: ocultar input y mostrar span
            const id = target.dataset.itemId;
            const span = target.parentElement.querySelector(`.val[data-item-id="${id}"]`);
            target.style.display = 'none';
            target.classList.remove('editing');
            if (span) span.style.display = 'inline-block';
            return;
        }
        if (e.key === 'Enter') {
            e.preventDefault();
            try { console.debug('payslip_modal: Enter pressed, saving', target.dataset.itemId, target.value); } catch(e){}
            // evitar envíos múltiples
            if (target.dataset.saving) return;

            // Formatear valor para mostrar optimistamente
            const raw = String(target.value||'');
            const parsedOptimistic = parseFloat(raw.replace(/[^0-9,.-]/g,'').replace(/,/g,'.'));
            if (isNaN(parsedOptimistic)) {
                if (typeof Swal !== 'undefined') Swal.fire({icon:'error', title:'Valor inválido', text:'Ingrese un número válido.'});
                return;
            }

            // Marcar como guardando y actualizar UI inmediatamente para prevenir múltiples Enter
            target.dataset.saving = '1';
            target.disabled = true;
            const id = target.dataset.itemId;
            const span = target.parentElement.querySelector(`.val[data-item-id="${id}"]`);
            if (span) {
                span.innerText = `$ ${parsedOptimistic.toFixed(2)}`;
                span.style.display = 'inline-block';
                span.classList.add('sealed');
            }
            target.style.display = 'none';
            target.classList.remove('editing');

            // Llamar al guardado real; si falla revertimos
            saveInputValue(target).then((res) => {
                try { delete target.dataset.saving; target.disabled = false; } catch(e){}
                if (!res || !res.ok) {
                    // Revertir UI al valor original
                    const original = target.dataset.original || '';
                    if (span) {
                        span.innerText = original ? `$ ${parseFloat(original).toFixed(2)}` : '';
                        span.classList.remove('sealed');
                    }
                    target.style.display = 'inline-block';
                    target.focus();
                    if (typeof Swal !== 'undefined') Swal.fire({icon:'error', title:'No guardado', text:'No se pudo guardar el valor.'});
                } else {
                    // mantener sellado (saveInputValue ya actualizó y ocultó input)
                }
            }).catch(err => {
                try { delete target.dataset.saving; target.disabled = false; } catch(e){}
                console.error('saveInputValue promise rejected', err);
            });
        }
    }

});

// Guardar al perder foco (focusout) sobre un input editable — listener global
document.addEventListener('focusout', function (ev) {
    const tgt = ev.target;
    if (tgt && tgt.classList && tgt.classList.contains('val-input') && tgt.classList.contains('editing')) {
        // guardamos el campo (no esperar para no bloquear UI)
        saveInputValue(tgt).then(() => {});
    }
}, true);

document.addEventListener('change', function (e) {
    // 2. SWITCH DE RETENCIÓN DE PAGO
    if (e.target.classList.contains('toggle-withhold-btn')) {
        const checkbox = e.target;
        let payslipId = checkbox.dataset.id || '';
        // Sanear el id por si viene con separadores de miles u otros caracteres
        payslipId = payslipId.toString().replace(/[^0-9]/g, '');
        const isChecked = checkbox.checked;

        let csrfToken = getCookie('csrftoken');

        fetch(`/payroll/payslip/${payslipId}/toggle-withhold/`, {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken}
        })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    // Actualizamos el estado del checkbox según respuesta del servidor
                    checkbox.checked = !!data.is_withheld;
                    // Ajustamos la apariencia: aplicamos clase amarilla cuando esté retenido
                    const wrapper = checkbox.closest('.modern-toggle-wrapper') || checkbox.parentElement;
                    if (wrapper) {
                        if (data.is_withheld) {
                            wrapper.classList.add('modern-toggle-yellow');
                        } else {
                            wrapper.classList.remove('modern-toggle-yellow');
                        }

                        // Actualizar el texto dentro del wrapper
                        const textEl = wrapper.querySelector('.modern-toggle-text');
                        if (textEl) {
                            textEl.textContent = data.is_withheld ? 'Retenido' : 'Normal';
                        }
                    }
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({toast: true, position: 'top-end', showConfirmButton: false, timer: 2000, icon: 'success', title: data.message});
                    }
                } else {
                    // Revertir el checkbox si hubo error
                    checkbox.checked = !isChecked;
                    if (typeof Swal !== 'undefined') {
                        Swal.fire({icon: 'error', title: 'Error', text: 'No se pudo actualizar el estado.'});
                    }
                }
            })
            .catch(() => {
                checkbox.checked = !isChecked;
                if (typeof Swal !== 'undefined') {
                    Swal.fire({icon: 'error', title: 'Error', text: 'Error de conexión.'});
                }
            });
    }
});

// Función de utilidad para obtener el CSRF Token en Django
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
