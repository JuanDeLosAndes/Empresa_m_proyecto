const pesos = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });
const estadoCarrito = document.querySelector('#estado-carrito');

async function modificarCarrito(control, eliminar) {
    if (eliminar && !confirm('¿Eliminar esta máquina del carrito?')) return;
    const unidad = control.closest('.carrito-item').querySelector('.unidad-alquiler');
    const cantidad = control.closest('.carrito-item').querySelector('.horas-input');
    const factor = Number(unidad.value);
    if (!eliminar && !cantidad.reportValidity()) {
        restaurarCantidad(cantidad, unidad);
        return;
    }
    const controles = document.querySelectorAll('.horas-input, .unidad-alquiler, .btn-eliminar, .btn-pagar');
    controles.forEach(elemento => elemento.disabled = true);
    estadoCarrito.textContent = 'Guardando…';
    try {
        const opciones = eliminar ? {method: 'DELETE'} : {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({horas: Number(cantidad.value) * factor})
        };
        const respuesta = await fetch('/api/carrito/items/' + control.dataset.id, opciones);
        const datos = await respuesta.json();
        if (!respuesta.ok) {
            throw new Error(typeof datos.detail === 'string' ? datos.detail : 'Escribe al menos una hora entera.');
        }
        if (eliminar) {
            location.reload();
            return;
        }
        cantidad.value = datos.horas / factor;
        cantidad.defaultValue = cantidad.value;
        unidad.dataset.guardada = unidad.value;
        control.closest('.carrito-item').querySelector('.total-precio').textContent = '$' + pesos.format(datos.total_linea) + ' COP';
        for (const [id, valor] of Object.entries({subtotal: datos.subtotal, impuesto: datos.iva, total: datos.total})) {
            document.getElementById(id).textContent = '$' + pesos.format(valor);
        }
        estadoCarrito.textContent = 'Duración actualizada: ' + datos.horas + ' h.';
    } catch (error) {
        if (!eliminar) restaurarCantidad(cantidad, unidad);
        estadoCarrito.textContent = error.message || 'No se pudo guardar el cambio.';
    } finally {
        controles.forEach(elemento => elemento.disabled = false);
    }
}
function restaurarCantidad(input, unidad) {
    unidad.value = unidad.dataset.guardada;
    input.max = Math.floor(2147483647 / Number(unidad.value));
    input.value = input.defaultValue;
}
document.querySelectorAll('.horas-input').forEach(input => {
    const unidad = input.closest('.carrito-item').querySelector('.unidad-alquiler');
    const horas = Number(input.value);
    if (horas % 24 === 0) {
        unidad.value = '24';
        input.defaultValue = horas / 24;
        input.value = input.defaultValue;
    }
    unidad.dataset.guardada = unidad.value;
    input.max = Math.floor(2147483647 / Number(unidad.value));
    unidad.addEventListener('change', () => {
        input.max = Math.floor(2147483647 / Number(unidad.value));
        modificarCarrito(input, false);
    });
    input.addEventListener('change', () => modificarCarrito(input, false));
});
document.querySelectorAll('.btn-eliminar').forEach(btn => btn.addEventListener('click', () => modificarCarrito(btn, true)));