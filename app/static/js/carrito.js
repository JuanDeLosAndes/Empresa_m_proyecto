const pesos = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });
const estadoCarrito = document.querySelector('#estado-carrito');

async function modificarCarrito(control, eliminar) {
    if (eliminar && !confirm('¿Eliminar esta máquina del carrito?')) return;
    const controles = document.querySelectorAll('.horas-input, .btn-eliminar, .btn-pagar');
    controles.forEach(elemento => elemento.disabled = true);
    estadoCarrito.textContent = 'Guardando…';
    try {
        const opciones = eliminar ? {method: 'DELETE'} : {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({horas: Number(control.value)})
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
        control.value = datos.horas;
        control.defaultValue = datos.horas;
        control.closest('.carrito-item').querySelector('.total-precio').textContent = '$' + pesos.format(datos.total_linea) + ' COP';
        for (const [id, valor] of Object.entries({subtotal: datos.subtotal, impuesto: datos.iva, total: datos.total})) {
            document.getElementById(id).textContent = '$' + pesos.format(valor);
        }
        estadoCarrito.textContent = 'Horas actualizadas.';
    } catch (error) {
        if (!eliminar) control.value = control.defaultValue;
        estadoCarrito.textContent = error.message || 'No se pudo guardar el cambio.';
    } finally {
        controles.forEach(elemento => elemento.disabled = false);
    }
}
document.querySelectorAll('.horas-input').forEach(input => input.addEventListener('change', () => modificarCarrito(input, false)));
document.querySelectorAll('.btn-eliminar').forEach(btn => btn.addEventListener('click', () => modificarCarrito(btn, true)));