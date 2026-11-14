(() => {
    const dialogo = document.querySelector('#alta-maquina');
    document.querySelectorAll('[data-abrir-alta]').forEach(boton => {
        boton.addEventListener('click', () => dialogo.showModal());
    });
    document.querySelector('[data-cerrar-alta]')?.addEventListener('click', () => dialogo.close());

    async function guardar(event, crear) {
        event.preventDefault();
        const form = event.currentTarget;
        const boton = form.querySelector('[type="submit"]');
        const estado = form.querySelector('.admin-estado');
        const datos = Object.fromEntries(new FormData(form));
        datos.costo_por_hora = Number(datos.costo_por_hora);
        datos.disponible = form.elements.disponible.checked;
        if (crear) datos.id_categoria = Number(datos.id_categoria);
        boton.disabled = true;
        estado.textContent = 'Guardando…';
        try {
            const respuesta = await fetch(crear ? '/admin/maquinas' : '/admin/maquinas/' + form.dataset.maquina, {
                method: crear ? 'POST' : 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(datos)
            });
            const resultado = await respuesta.json();
            if (!respuesta.ok) {
                throw new Error(typeof resultado.detail === 'string' ? resultado.detail : 'Revisa los campos del formulario.');
            }
            if (crear) location.href = '/maquina/' + resultado.id_maquinaria;
            else location.reload();
        } catch (error) {
            estado.textContent = error.message || 'No se pudo guardar. Intenta nuevamente.';
            boton.disabled = false;
        }
    }
    document.querySelector('#form-alta-maquina')?.addEventListener('submit', event => guardar(event, true));
    document.querySelector('#form-editar-maquina')?.addEventListener('submit', event => guardar(event, false));

    const subida = document.querySelector('#subir-fotos-detalle');
    subida?.querySelector('input[type="file"]').addEventListener('change', () => {
        if (!subida.elements.archivos.files.length) return;
        subida.querySelector('[role="status"]').textContent = 'Subiendo imágenes…';
        subida.requestSubmit();
    });
})();