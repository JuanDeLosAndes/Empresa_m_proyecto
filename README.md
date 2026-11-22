# Empresa_m_proyecto

## Persistencia de MSPS

| Información | Almacenamiento |
|---|---|
| Cuentas, empresas, catálogo, afiliaciones, cotizaciones, alquileres, facturas y pedidos de pago | PostgreSQL en Azure o SQLite local |
| Fichas de fabricante y referencias a imágenes por placa | MongoDB Atlas, colección `maquinas` |
| Archivos de fotos | MongoDB GridFS, colecciones `fs.files` y `fs.chunks` |
| Selección actual de máquinas y horas del carrito | Sesión firmada del navegador |

La aplicación crea las 15 tablas al arrancar. Los esquemas están en `app/schema.sql` y `app/schema_postgres.sql`.
En una PostgreSQL nueva, la carga inicial añade las máquinas predefinidas. Si se ha importado un catálogo antes del primer arranque, no agrega máquinas predefinidas adicionales. El administrador sube sus fotos desde la web.
El modelo enlaza cada fila de maquinaria con su documento MongoDB mediante la placa.

### Ejecutar y comprobar

1. Instala Python 3.12 y las dependencias con `python -m pip install -r requirements.txt`.
2. Usa `.env.servicios.example` y `.env.correo.example` como referencia para las variables de tu entorno.
3. En desarrollo, ejecuta `python -m uvicorn main:app --reload`. SQLite toma la ruta de `MSPS_DB_PATH`.
4. En Azure configura `MSPS_DB_ENGINE=postgresql`, los valores `PG*` del ejemplo, una clave de sesión fija y la contraseña inicial del administrador. El comando de inicio es `sh startup.sh`.
5. Entra como administrador y abre `/admin/diagnostico` para ver el motor activo, las tablas y campos presentes y la conexión con MongoDB.

La herramienta `python -m tools.preparar_postgres_azure` prepara la base `msps` y el usuario `msps_app` en un servidor PostgreSQL ya creado. Para conservar **solo categorías y máquinas** de SQLite, crea primero las tablas con `MSPS_DB_ENGINE=postgresql python -c 'from app.database import init_db; init_db()'` y ejecuta `MSPS_DB_ENGINE=postgresql python -m tools.importar_sqlite_a_postgres --solo-catalogo RUTA_SQLITE`. Las fotos permanecen en MongoDB Atlas y se vinculan por placa. Este modo no traslada usuarios, empresas, facturas ni pedidos: al arrancar, la aplicación crea el administrador con `MSPS_ADMIN_PASSWORD`. Para un traslado completo a una PostgreSQL sin tablas MSPS todavía existe `python -m tools.importar_sqlite_a_postgres RUTA_SQLITE`.

### Organización MVC

- Los controladores de `app/controllers/` reciben formularios, aplican las dependencias de sesión y traducen los resultados del modelo a HTML o JSON.
- Los modelos de `app/models/` definen los importes, la disponibilidad, la afiliación, la propiedad de los pedidos y las transiciones de pago. Los modelos relacionales sencillos encapsulan sus consultas. Los repositorios de `app/repositories/` guardan y recuperan los pedidos, el carrito de sesión y los documentos.
- Las vistas de `app/templates/` presentan los resultados. El CSS y los eventos del navegador de la ficha de maquinaria están en `app/static/`. Los campos de formulario se definen en `app/views/formularios.py`.
- Al cambiar las horas, la ficha llama a `GET /api/maquinas/{id}/estimacion`. El controlador consulta `CarritoModel` y la vista muestra el importe de la línea. El checkout usa el mismo modelo para el subtotal, el IVA y el total.

### Pruebas

Instala las dependencias de pruebas con `python -m pip install pytest mongomock` y ejecuta `python -m pytest -q`. La suite usa SQLite temporal y MongoDB simulado. Para incluir PostgreSQL, indica las variables `PG*` de una base desechable cuyo nombre termine en `_test`, concede al usuario de prueba permiso para crear esquemas en esa base y define `MSPS_TEST_POSTGRES=1`. Los avisos y consultas de Wompi se prueban con respuestas simuladas.

### Patrones y principios

- **Singleton:** `MongoConnection` (`app/documentos/store.py`).
- **Factory Method:** `FichaTecnicaFactory`, `crear_maquina_documentos_repositorio()`, `crear_imagenes_repositorio()`.
- **Builder + Director:** `MaquinaDocumentoBuilder` y `CatalogoDirector`.
- **SOLID:** repositorios con interfaces separadas de lectura y escritura (ISP), los controladores dependen de
  esas interfaces y no de pymongo (DIP), un tipo de ficha nuevo se agrega sin tocar código existente (OCP).

### Revisión del catálogo y de las cuentas

Al crear una máquina, el administrador ingresa al menos una característica con su valor
y unidad. La ficha y el alta se guardan en la misma transacción SQL. El administrador
también puede editarlas en el detalle. Para equipos anteriores se usa su ficha de
fabricante o, en su ausencia, las especificaciones que ya figuran en el catálogo.

Registro y recuperación validan los datos en el navegador y en el servidor. Al crear
o cambiar una contraseña se exigen ocho números, una mayúscula y un símbolo.
Las cuentas existentes conservan el acceso con su contraseña anterior.

Para recibir los enlaces, configura un remitente SMTP autorizado. En el desarrollo local
agrega al archivo `.env` los valores de `.env.correo.example`. En Azure coloca los mismos
nombres en las variables de entorno de la aplicación web. Ajusta `PUBLIC_BASE_URL` al
origen desde el que el destinatario abrirá la aplicación. Para Azure usa el dominio HTTPS
de la aplicación. Los puertos admitidos habitualmente son 587 con STARTTLS y 465 con TLS.
Las claves se configuran localmente o en Azure. Los enlaces caducan a los 30 minutos y
la base conserva solo su huella.

Los componentes en `app/views/` preparan el contexto y los campos para Jinja. Las rutas en
`app/controllers/` traducen formularios y JSON en operaciones de los modelos. El modelo
de recuperación recibe una función que entrega el enlace. Producción utiliza el transporte
SMTP de `app/services/correo.py` y las pruebas pueden sustituirlo. Esta separación
mantiene las reglas de cuentas independientes de SMTP y permite probarlas de forma aislada.

Swagger está disponible en `/docs`. Para probar las operaciones de administrador,
inicia sesión en la web y abre Swagger en el mismo navegador. El carrito cubre PATCH,
y el alta, consulta, edición y baja de máquinas cubren POST, GET, PUT y DELETE.

### Cómo comprobar los principios SOLID en esta entrega

| Principio | Ejemplo verificable |
|---|---|
| Responsabilidad única | La política de credenciales valida texto, el modelo de recuperación gestiona los tokens y el servicio SMTP entrega el mensaje. |
| Abierto/cerrado | La colección de tipos de ficha del fabricante se amplía registrando una subclase en la fábrica. La ficha del administrador acepta características distintas según el equipo. |
| Sustitución de Liskov | La prueba de contrato ejecuta las mismas operaciones de guardar, leer y eliminar contra GridFS y contra su proxy con caché. |
| Segregación de interfaces | La galería recibe contratos con las operaciones de imágenes y documentos que necesita. Los repositorios de lectura y escritura tienen interfaces separadas. |
| Inversión de dependencias | Registro y recuperación reciben la función encargada del envío. Sus reglas se ejercitan con un remitente de prueba y se conectan al transporte SMTP desde el controlador. |
