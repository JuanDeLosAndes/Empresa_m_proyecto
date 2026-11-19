PRAGMA foreign_keys = ON;


CREATE TABLE IF NOT EXISTS roles (
    id_rol  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL UNIQUE
);

INSERT OR IGNORE INTO roles (nombre) VALUES ('empresa');
INSERT OR IGNORE INTO roles (nombre) VALUES ('administrador');
INSERT OR IGNORE INTO roles (nombre) VALUES ('persona_natural');


CREATE TABLE IF NOT EXISTS empresas (
    id_empresa      INTEGER PRIMARY KEY AUTOINCREMENT,
    nit             TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    correo          TEXT NOT NULL UNIQUE,
    direccion       TEXT,
    contrasena_hash TEXT NOT NULL,
    fecha_registro  TEXT NOT NULL DEFAULT (datetime('now')),
    id_rol          INTEGER NOT NULL DEFAULT 1 REFERENCES roles(id_rol)
);


CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    contrasena_hash TEXT NOT NULL,
    id_empresa      INTEGER REFERENCES empresas(id_empresa) ON DELETE SET NULL,
    id_rol          INTEGER NOT NULL REFERENCES roles(id_rol),
    fecha_registro  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usuarios_id_empresa ON usuarios(id_empresa);
CREATE INDEX IF NOT EXISTS idx_usuarios_id_rol ON usuarios(id_rol);


CREATE TABLE IF NOT EXISTS personas_naturales (
    id_persona_natural INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario         INTEGER NOT NULL UNIQUE REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    cedula             TEXT NOT NULL UNIQUE,
    correo             TEXT NOT NULL UNIQUE,
    telefono           TEXT
);


CREATE TABLE IF NOT EXISTS administradores (
    id_administrador INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario       INTEGER NOT NULL UNIQUE REFERENCES usuarios(id_usuario) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS categorias (
    id_categoria     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_categoria TEXT NOT NULL UNIQUE
);


CREATE TABLE IF NOT EXISTS maquinarias (
    id_maquinaria   INTEGER PRIMARY KEY AUTOINCREMENT,
    marca           TEXT NOT NULL,
    descripcion     TEXT,
    capacidad       TEXT,
    modelo          TEXT,
    costo_por_hora  REAL NOT NULL CHECK (costo_por_hora >= 0),
    placa           TEXT NOT NULL UNIQUE,
    disponible      INTEGER NOT NULL DEFAULT 1 CHECK(disponible IN (0, 1)),
    id_categoria    INTEGER NOT NULL REFERENCES categorias(id_categoria) ON DELETE RESTRICT,
    eliminada       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_maquinarias_id_categoria ON maquinarias(id_categoria);


CREATE TABLE IF NOT EXISTS alquileres (
    id_alquiler       INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_inicio      TEXT NOT NULL,
    fecha_fin         TEXT,
    estado_ocupacion  TEXT NOT NULL DEFAULT 'ocupada'
                          CHECK (estado_ocupacion IN ('ocupada', 'desocupada')),
    estado_aprobacion TEXT NOT NULL DEFAULT 'pendiente'
                          CHECK (estado_aprobacion IN ('pendiente', 'aprobado', 'rechazado')),
    id_usuario        INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    id_maquinaria     INTEGER NOT NULL REFERENCES maquinarias(id_maquinaria) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_alquileres_id_usuario ON alquileres(id_usuario);
CREATE INDEX IF NOT EXISTS idx_alquileres_id_maquinaria ON alquileres(id_maquinaria);


CREATE TABLE IF NOT EXISTS facturas (
    id_factura    INTEGER PRIMARY KEY AUTOINCREMENT,
    numero        TEXT NOT NULL UNIQUE,
    cedula        TEXT NOT NULL,
    metodo_pago   TEXT NOT NULL,
    costo         REAL NOT NULL CHECK (costo >= 0),
    iva           REAL NOT NULL CHECK (iva >= 0),
    fecha         TEXT NOT NULL DEFAULT (datetime('now')),
    id_alquiler   INTEGER NOT NULL REFERENCES alquileres(id_alquiler) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_facturas_id_alquiler ON facturas(id_alquiler);



CREATE TABLE IF NOT EXISTS facturas_empresa (
    id_factura_empresa INTEGER PRIMARY KEY AUTOINCREMENT,
    nit           TEXT NOT NULL,
    correo        TEXT NOT NULL,
    metodo_pago   TEXT NOT NULL,
    costo         REAL NOT NULL CHECK (costo >= 0),
    fecha         TEXT NOT NULL DEFAULT (datetime('now')),
    id_alquiler   INTEGER NOT NULL REFERENCES alquileres(id_alquiler) ON DELETE RESTRICT,
    id_empresa    INTEGER NOT NULL REFERENCES empresas(id_empresa) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_facturas_empresa_id_alquiler ON facturas_empresa(id_alquiler);
CREATE INDEX IF NOT EXISTS idx_facturas_empresa_id_empresa ON facturas_empresa(id_empresa);


CREATE TABLE IF NOT EXISTS solicitudes_empresa (
    id_usuario INTEGER PRIMARY KEY REFERENCES personas_naturales(id_usuario) ON DELETE CASCADE,
    id_empresa INTEGER NOT NULL REFERENCES empresas(id_empresa) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cotizaciones (
    id_cotizacion INTEGER PRIMARY KEY,
    id_maquinaria INTEGER NOT NULL REFERENCES maquinarias(id_maquinaria),
    nombre TEXT NOT NULL,
    email TEXT NOT NULL,
    telefono TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    creada TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS registros_pendientes (
    token_hash TEXT PRIMARY KEY,
    correo TEXT NOT NULL UNIQUE,
    tipo TEXT NOT NULL CHECK(tipo IN ('persona', 'empresa')),
    datos TEXT NOT NULL,
    creado INTEGER NOT NULL,
    vence INTEGER NOT NULL
);



-- Pedidos de pago: conserva el precio y las horas que se confirmaron al pagar.
-- La identidad del comprador incluye el tipo: empresas y usuarios tienen IDs distintos.
CREATE TABLE IF NOT EXISTS pedidos_pago (
    referencia TEXT PRIMARY KEY,
    propietario_tipo TEXT NOT NULL,
    propietario_id INTEGER NOT NULL,
    nombre TEXT NOT NULL,
    correo TEXT NOT NULL,
    ambiente TEXT NOT NULL CHECK(ambiente IN ('test', 'prod')),
    huella TEXT NOT NULL,
    lineas_json TEXT NOT NULL,
    subtotal_centavos INTEGER NOT NULL CHECK(subtotal_centavos >= 0),
    iva_centavos INTEGER NOT NULL CHECK(iva_centavos >= 0),
    total_centavos INTEGER NOT NULL CHECK(total_centavos > 0),
    estado TEXT NOT NULL DEFAULT 'PENDING'
        CHECK(estado IN ('PENDING', 'APPROVED', 'DECLINED', 'ERROR', 'VOIDED')),
    transaccion_id TEXT UNIQUE,
    metodo_pago TEXT,
    creada INTEGER NOT NULL,
    vence INTEGER NOT NULL,
    vence_iso TEXT NOT NULL,
    pagada INTEGER,
    actualizada INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_pedidos_propietario
ON pedidos_pago(propietario_tipo, propietario_id, creada DESC);
CREATE INDEX IF NOT EXISTS idx_pedidos_pendientes
ON pedidos_pago(propietario_tipo, propietario_id, ambiente, huella, estado);


