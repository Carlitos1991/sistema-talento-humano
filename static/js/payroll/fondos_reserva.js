// JS para Fondos de Reserva: toggles y guardado inmediato via AJAX
(function(){
    function getCsrfToken(){
        // Leer cookie csrftoken
        const name = 'csrftoken=';
        const cookies = document.cookie.split(';');
        for(let i=0;i<cookies.length;i++){
            let c = cookies[i].trim();
            if(c.indexOf(name)===0) return c.substring(name.length);
        }
        // fallback a input hidden
        const el = document.querySelector('[name="csrfmiddlewaretoken"]');
        return el ? el.value : '';
    }

    function toggleHandler(e){
        const input = e.target;
        if(!input.classList.contains('fr-checkbox')) return;
        const personId = input.dataset.personId;
        const field = input.dataset.field;
        if(!personId || !field) return;

        // Mostrar estado optimista en UI
        const wrapper = document.querySelector('label[for="' + (input.id || '') + '"]');
        const textEl = wrapper && wrapper.querySelector('.modern-toggle-text');
        const checked = input.checked;
        if(checked){
            wrapper.classList.add('modern-toggle-green');
            if(textEl) textEl.textContent = 'Mensualiza';
        } else {
            wrapper.classList.remove('modern-toggle-green');
            if(textEl) textEl.textContent = 'Acumula';
        }

        // Preparar payload FormData
        const url = '/employee/person/' + personId + '/update-payroll-info/';
        const formData = new FormData();
        // A BooleanField expects 'on' when checked; omit when false
        // Mapear nombre de campo de UI (español) al nombre esperado por el backend
        if(field === 'reserve_funds' || field === 'fondos_reserva'){
            if(checked) formData.append('reserve_funds', 'on');
        } else if(field === 'monthly_payment'){
            if(checked) formData.append('monthly_payment', 'on');
        }
        // CSRF handled via header

        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCsrfToken()
            }
        }).then(resp => resp.json())
        .then(data => {
            if(!data || data.success === false){
                // Revertir estado UI y mostrar error
                input.checked = !checked;
                const rollbackWrapper = document.querySelector('label[for="' + (input.id || '') + '"]');
                if(input.checked){
                    if(rollbackWrapper) rollbackWrapper.classList.add('modern-toggle-green');
                    if(textEl) textEl.textContent = 'Mensualiza';
                } else {
                    if(rollbackWrapper) rollbackWrapper.classList.remove('modern-toggle-green');
                    if(textEl) textEl.textContent = 'Acumula';
                }
                const msg = (data && data.message) ? data.message : 'No se pudo actualizar la información.';
                if(window.Swal) Swal.fire('Error', msg, 'error'); else alert(msg);
            }
        }).catch(err => {
            // Revertir UI y notificar
            input.checked = !checked;
            const rollbackWrapper2 = document.querySelector('label[for="' + (input.id || '') + '"]');
            if(input.checked){
                if(rollbackWrapper2) rollbackWrapper2.classList.add('modern-toggle-green');
                if(textEl) textEl.textContent = 'Mensualiza';
            } else {
                if(rollbackWrapper2) rollbackWrapper2.classList.remove('modern-toggle-green');
                if(textEl) textEl.textContent = 'Acumula';
            }
            if(window.Swal) Swal.fire('Error', 'Error de comunicación: ' + err.message, 'error'); else alert('Error de comunicación: ' + err.message);
        });
    }

    document.addEventListener('change', function(e){
        // Delegación para inputs checkbox dinámicos
        toggleHandler(e);
    });
})();
