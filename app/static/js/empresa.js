async function guardarAccion(boton, url, method, cuerpo) {
    const estado = document.querySelector('#estado-equipo');
    boton.disabled = true;
    try {
        const opciones = {method};
        if (cuerpo) {
            opciones.headers = {'Content-Type': 'application/json'};
            opciones.body = JSON.stringify(cuerpo);
        }
        const respuesta = await fetch(url, opciones);
        if (!respuesta.ok) {
            const datos = await respuesta.json();
            throw new Error(typeof datos.detail === 'string' ? datos.detail : 'Revisa la solicitud.');
        }
        location.reload();
    } catch (error) {
        estado.textContent = error.message;
        boton.disabled = false;
    }
}
document.querySelector('#solicitar-ingreso')?.addEventListener('submit', event => {
    event.preventDefault();
    guardarAccion(event.submitter, '/api/empresa/solicitudes', 'POST', {
        id_empresa: Number(document.querySelector('#empresa').value)
    });
});
document.querySelectorAll('[data-accion]').forEach(boton => boton.addEventListener('click', () => {
    const {accion, usuario} = boton.dataset;
    if (accion === 'retirar') {
        const nombre = boton.closest('.equipo-fila').querySelector('strong').textContent;
        if (confirm('¿Retirar a ' + nombre + ' de tu empresa? Su cuenta personal seguirá activa.')) {
            guardarAccion(boton, '/api/empresa/integrantes/' + usuario, 'DELETE');
        }
    } else {
        guardarAccion(boton, '/api/empresa/solicitudes/' + usuario, 'PATCH', {aceptar: accion === 'aceptar'});
    }
}));