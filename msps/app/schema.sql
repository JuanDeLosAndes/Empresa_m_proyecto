PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- ROL  (catálogo de roles del sistema)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS roles (
    id_rol  INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL UNIQUE
);

-- El orden importa: 'empresa' debe quedar con id 1 (es el DEFAULT de empresas.id_rol).
INSERT OR IGNORE INTO roles (nombre) VALUES ('empresa');
INSERT OR IGNORE INTO roles (nombre) VALUES ('administrador');
INSERT OR IGNORE INTO roles (nombre) VALUES ('persona_natural');

-- ---------------------------------------------------------------------
-- EMPRESA
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- USUARIO  (cuenta base: la comparten personas naturales y administradores)
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- PERSONA NATURAL  (datos propios de un usuario con rol persona_natural)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS personas_naturales (
    id_persona_natural INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario         INTEGER NOT NULL UNIQUE REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
    cedula             TEXT NOT NULL UNIQUE,
    correo             TEXT NOT NULL UNIQUE,
    telefono           TEXT
);

-- ---------------------------------------------------------------------
-- ADMINISTRADOR  (un usuario con rol administrador)
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS administradores (
    id_administrador INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario       INTEGER NOT NULL UNIQUE REFERENCES usuarios(id_usuario) ON DELETE CASCADE
);

-- ---------------------------------------------------------------------
-- CATEGORIA
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria     INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_categoria TEXT NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------
-- MAQUINARIA
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS maquinarias (
    id_maquinaria   INTEGER PRIMARY KEY AUTOINCREMENT,
    marca           TEXT NOT NULL,
    descripcion     TEXT,
    capacidad       TEXT,
    modelo          TEXT,
    costo_por_hora  REAL NOT NULL CHECK (costo_por_hora >= 0),
    placa           TEXT NOT NULL UNIQUE,
    id_categoria    INTEGER NOT NULL REFERENCES categorias(id_categoria) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_maquinarias_id_categoria ON maquinarias(id_categoria);

-- ---------------------------------------------------------------------
-- ALQUILER  (relaciona Usuario <-> Maquinaria)
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- FACTURA  (factura a persona natural)
-- ---------------------------------------------------------------------
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

-- ---------------------------------------------------------------------
-- FACTURA EMPRESA
-- ---------------------------------------------------------------------
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