(() => {
    const dialogo = document.querySelector('#alta-maquina');
    document.querySelectorAll('[data-abrir-alta]').forEach(boton => {
        boton.addEventListener('click', () => dialogo.showModal());
    });
    document.querySelector('[data-cerrar-alta]')?.addEventListener('click', () => dialogo.close());

    document.querySelectorAll('.ficha-editor').forEach(editor => {
        const filas = editor.querySelector('[data-filas-ficha]');
        editor.addEventListener('click', event => {
            if (event.target.closest('[data-nueva-fila]') && filas.children.length < 32) {
                const nueva = filas.firstElementChild.cloneNode(true);
                nueva.querySelectorAll('input').forEach(input => input.value = '');
                filas.append(nueva);
                nueva.querySelector('input').focus();
            }
            if (event.target.closest('[data-quitar]') && filas.children.length > 1) {
                event.target.closest('.ficha-fila').remove();
            }
        });
    });

    async function guardar(event, crear) {
        event.preventDefault();
        const form = event.currentTarget;
        const boton = form.querySelector('[type="submit"]');
        const estado = form.querySelector('.admin-estado');
        const datos = Object.fromEntries(new FormData(form));
        const ficha = new Map();
        for (const fila of form.querySelectorAll('.ficha-fila')) {
            const clave = fila.querySelector('[data-etiqueta]').value.trim();
            const valor = fila.querySelector('[data-valor]').value.trim();
            if (!clave || !valor || ficha.has(clave)) {
                estado.textContent = 'Completa cada característica y evita nombres repetidos.';
                return;
            }
            ficha.set(clave, valor);
        }
        datos.ficha_tecnica = Object.fromEntries(ficha);
        delete datos.archivos;
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
            if (crear) {
                const archivos = form.elements.archivos.files;
                const destino = '/maquina/' + resultado.id_maquinaria;
                if (archivos.length) {
                    const carga = new FormData();
                    for (const archivo of archivos) carga.append('archivos', archivo);
                    try {
                        const subida = await fetch('/admin/maquinas/' + resultado.id_maquinaria + '/fotos', {
                            method: 'POST', body: carga
                        });
                        location.href = subida.ok ? subida.url : destino + '?error=mongo';
                    } catch (error) {
                        location.href = destino + '?error=mongo';
                    }
                } else location.href = destino;
            }
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

document.querySelector('[data-eliminar-maquina]')?.addEventListener('click', async event => {
    if (!confirm('¿Estás seguro de eliminar esta máquina del catálogo?')) return;
    const boton = event.currentTarget;
    boton.disabled = true;
    try {
        const respuesta = await fetch('/admin/maquinas/' + boton.dataset.eliminarMaquina, {method: 'DELETE'});
        if (!respuesta.ok) throw new Error('No se pudo eliminar la máquina.');
        location.href = '/maquinas';
    } catch (error) {
        document.querySelector('#form-editar-maquina .admin-estado').textContent = error.message;
        boton.disabled = false;
    }
});