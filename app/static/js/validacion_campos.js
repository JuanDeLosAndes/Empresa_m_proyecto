document.querySelectorAll('.auth-panel__form, #modal-cotizacion form, .admin-form').forEach((form, indice) => {
    const controles = form.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]), textarea, select');
    controles.forEach((input, posicion) => {
        const aviso = document.createElement('small');
        aviso.className = 'campo-error';
        aviso.id = 'error-' + indice + '-' + posicion;
        aviso.setAttribute('aria-live', 'polite');
        input.after(aviso);
        input.setAttribute('aria-describedby', [input.getAttribute('aria-describedby'), aviso.id].filter(Boolean).join(' '));

        function validar() {
            let mensaje = '';
            if (input.validity.customError) mensaje = input.validationMessage;
            else if (input.validity.valueMissing) mensaje = 'Completa este campo.';
            else if (!input.validity.valid) {
                if (input.type === 'email') mensaje = 'Esto no parece un correo electrónico. Ejemplo: nombre@dominio.com.';
                else mensaje = input.title || 'Revisa el formato de este campo.';
            }
            aviso.textContent = mensaje;
            input.setAttribute('aria-invalid', String(Boolean(mensaje)));
        }
        if (input.name === 'telefono' && input.inputMode === 'numeric') {
            input.addEventListener('beforeinput', event => {
                if (event.cancelable && event.inputType.startsWith('insert') && /[^0-9]/.test(event.data || '')) {
                    event.preventDefault();
                    aviso.textContent = input.title;
                }
            });
        }
        input.addEventListener('invalid', event => {
            event.preventDefault();
            validar();
            if (form.querySelector(':invalid') === input) input.focus();
        });
        input.addEventListener('blur', event => {
            // Al pulsar Enviar, el navegador valida todos los campos antes del submit.
            // Evita desplazar el botón entre el mousedown y el click.
            if (event.relatedTarget?.type === 'submit' && event.relatedTarget.form === form) return;
            if (input.value || input.getAttribute('aria-invalid') === 'true') validar();
        });
        input.addEventListener('input', () => {
            input.setCustomValidity('');
            if (input.name === 'telefono' || input.getAttribute('aria-invalid') === 'true') validar();
        });
        form.addEventListener('reset', () => {
            input.setCustomValidity('');
            input.removeAttribute('aria-invalid');
            aviso.textContent = '';
        });
    });
});