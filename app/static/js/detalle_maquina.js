const contenedor = document.querySelector('.detalle-container');
const maquinaId = parseInt(contenedor.dataset.id);
let esperaEstimacion;
let versionEstimacion = 0;

function incrementarHoras() {
    const input = document.getElementById('cantidad-horas');
    input.value = (parseInt(input.value) || 1) + 1;
    actualizarTotal();
}

function decrementarHoras() {
    const input = document.getElementById('cantidad-horas');
    if (parseInt(input.value) > 1) {
        input.value = parseInt(input.value) - 1;
        actualizarTotal();
    }
}

function actualizarTotal() {
    const horas = Number(inputHoras.value);
    const etiqueta = document.getElementById('total-estimado');
    const version = ++versionEstimacion;
    clearTimeout(esperaEstimacion);
    if (!Number.isSafeInteger(horas) || horas < 1) {
        etiqueta.textContent = 'Escribe un número entero de horas mayor que cero.';
        return;
    }
    etiqueta.textContent = 'Calculando…';
    esperaEstimacion = setTimeout(async () => {
        try {
            const respuesta = await fetch('/api/maquinas/' + maquinaId + '/estimacion?horas=' + horas);
            if (!respuesta.ok) throw new Error();
            const linea = await respuesta.json();
            if (version === versionEstimacion) {
                etiqueta.textContent = '$' + linea.total_linea.toLocaleString('es-CO', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' COP';
            }
        } catch {
            if (version === versionEstimacion) etiqueta.textContent = 'No se pudo consultar el precio.';
        }
    }, 250);
}

const inputHoras = document.getElementById('cantidad-horas');
if (inputHoras) inputHoras.addEventListener('input', actualizarTotal);

// Galería: al pulsar una miniatura se cambia la imagen principal.
const imagenPrincipal = document.getElementById('imagen-principal');
document.querySelectorAll('.detalle-miniatura').forEach(btn => {
    btn.addEventListener('click', () => {
        imagenPrincipal.src = btn.dataset.src;
        imagenPrincipal.alt = btn.dataset.alt;
        document.querySelectorAll('.detalle-miniatura').forEach(b => b.classList.remove('activa'));
        btn.classList.add('activa');
    });
});

function agregarAlCarrito() {
    if (!inputHoras.reportValidity()) return;
    fetch('/api/verificar-login', { method: 'GET', credentials: 'same-origin' })
        .then(res => res.json())
        .then(data => {
            if (!data.logueado) {

                document.dispatchEvent(new Event('msps:login'));
                return;
            }
            return fetch('/api/carrito/items', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'same-origin',
                body: JSON.stringify({
                    id_maquinaria: maquinaId,
                    horas: Math.max(1, parseInt(document.getElementById('cantidad-horas').value) || 1)
                })
            })
            .then(async res => {
                const datos = await res.json();
                if (!res.ok) throw new Error(typeof datos.detail === 'string' ? datos.detail : 'No se pudo agregar la máquina.');
                return datos;
            })
            .then(data => {
                if (data.status === 'ok') {
                    window.location.href = '/carrito';
                }
            });
        })
        .catch(err => {
            console.error('Error agregar al carrito:', err);
            document.querySelector('#estado-agregar').textContent = err.message;
        });
}

function cotizar() {
    document.getElementById('modal-cotizacion').style.display = 'flex';
}

function cerrarModal() {
    document.getElementById('modal-cotizacion').style.display = 'none';
}

async function enviarCotizacion(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const boton = form.querySelector('button[type="submit"]');
    const estado = document.querySelector('#estado-cotizacion');
    boton.disabled = true;
    estado.textContent = 'Enviando…';
    try {
        const datos = Object.fromEntries(new FormData(form));
        datos.id_maquinaria = maquinaId;
        const respuesta = await fetch('/cotizaciones', {
            method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(datos)
        });
        const resultado = await respuesta.json();
        if (!respuesta.ok) {
            throw new Error(typeof resultado.detail === 'string' ? resultado.detail : 'Revisa los datos de contacto y la longitud del mensaje.');
        }
        form.reset();
        estado.textContent = '';
        cerrarModal();
        const aviso = document.querySelector('#cotizacion-confirmada');
        aviso.textContent = 'Cotización #' + resultado.id_cotizacion + ' recibida.';
        aviso.scrollIntoView({block: 'center'});
    } catch (error) {
        estado.textContent = error.message;
    } finally {
        boton.disabled = false;
    }
}

function actualizarContadorCarrito() {
    fetch('/api/carrito/cantidad', { credentials: 'same-origin' })
        .then(res => res.json())
        .then(data => {
            const badge = document.getElementById('carrito-contador');
            if (!badge) return;
            if (data.cantidad > 0) {
                badge.textContent = data.cantidad;
                badge.style.display = 'flex';
            } else {
                badge.style.display = 'none';
            }
        })
        .catch(err => console.error('Error contador carrito:', err));
}

actualizarContadorCarrito();

window.onclick = function(event) {
    const modal = document.getElementById('modal-cotizacion');
    if (event.target === modal) {
        cerrarModal();
    }
}