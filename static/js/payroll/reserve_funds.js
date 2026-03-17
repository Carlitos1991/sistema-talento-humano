// JS for Reserve Funds: toggles and immediate save via AJAX
(function(){
    function getCsrfToken(){
        const name = 'csrftoken=';
        const cookies = document.cookie.split(';');
        for(let i=0;i<cookies.length;i++){
            let c = cookies[i].trim();
            if(c.indexOf(name)===0) return c.substring(name.length);
        }
        const el = document.querySelector('[name="csrfmiddlewaretoken"]');
        return el ? el.value : '';
    }

    function toggleHandler(e){
        const input = e.target;
        if(!input.classList.contains('fr-checkbox')) return;
        const personId = input.dataset.personId;
        const field = input.dataset.field;
        if(!personId || !field) return;

        const wrapper = document.querySelector('label[for="' + (input.id || '') + '"]');
        const textEl = wrapper && wrapper.querySelector('.modern-toggle-text');
        const checked = input.checked;
        if(checked){
            if(wrapper) wrapper.classList.add('modern-toggle-green');
            if(textEl) textEl.textContent = 'Mensualiza';
        } else {
            if(wrapper) wrapper.classList.remove('modern-toggle-green');
            if(textEl) textEl.textContent = 'Acumula';
        }

        const url = '/employee/person/' + personId + '/update-payroll-info/';
        const formData = new FormData();
        if(field === 'reserve_funds' || field === 'fondos_reserva'){
            if(checked) formData.append('reserve_funds', 'on');
        } else if(field === 'monthly_payment'){
            if(checked) formData.append('monthly_payment', 'on');
        }

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
                input.checked = !checked;
                const rollbackWrapper = document.querySelector('label[for="' + (input.id || '') + '"]');
                if(input.checked){
                    if(rollbackWrapper) rollbackWrapper.classList.add('modern-toggle-green');
                    if(textEl) textEl.textContent = 'Monthly';
                } else {
                    if(rollbackWrapper) rollbackWrapper.classList.remove('modern-toggle-green');
                    if(textEl) textEl.textContent = 'Accumulate';
                }
                const msg = (data && data.message) ? data.message : 'No se pudo actualizar la información.';
                if(window.Swal) Swal.fire('Error', msg, 'error'); else alert(msg);
            }
        }).catch(err => {
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
        toggleHandler(e);
    });
})();
