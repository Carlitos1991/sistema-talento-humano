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

        // Prefer server-provided URL if available (pre-rendered in data attribute)
        const url = input.dataset.updateUrl || ('/employee/person/' + personId + '/update-payroll-info/');
        // To avoid form validation errors, fetch current payroll info and send full payload
        const infoUrl = '/employee/person/' + personId + '/get-payroll-info/';
        fetch(infoUrl, { credentials: 'same-origin', headers: {'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json'} })
        .then(r => { if(!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(infoResp => {
            const current = (infoResp && infoResp.success && infoResp.data) ? infoResp.data : {};
            const formData = new FormData();
            // set booleans: append 'on' when true
            const monthly = (field === 'monthly_payment') ? checked : !!current.monthly_payment;
            const reserve = (field === 'reserve_funds' || field === 'fondos_reserva') ? checked : !!current.reserve_funds;
            if(monthly) formData.append('monthly_payment', 'on');
            if(reserve) formData.append('reserve_funds', 'on');
            // numeric/text fields: preserve existing values
            if(typeof current.family_dependents !== 'undefined') formData.append('family_dependents', String(current.family_dependents));
            if(typeof current.education_dependents !== 'undefined') formData.append('education_dependents', String(current.education_dependents));
            if(current.roles_entry_date) formData.append('roles_entry_date', current.roles_entry_date);
            if(typeof current.roles_count !== 'undefined') formData.append('roles_count', String(current.roles_count));

            // debug: log URL and payload
            try{ console.debug('ReserveFunds: POST', url, Array.from(formData.entries())); } catch(e){}

            return fetch(url, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken(),
                    'Accept': 'application/json'
                },
                credentials: 'same-origin'
            });
        })
        .then(resp => {
            if(!resp.ok){
                // show server error
                throw new Error('HTTP ' + resp.status);
            }
            return resp.json();
        })
        .then(data => {
            if(!data || data.success === false){
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
