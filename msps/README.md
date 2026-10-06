# Empresa_m_proyecto

## Base de datos no relacional (MongoDB)

Las fichas técnicas y las **fotos** de las máquinas viven en MongoDB:

| Qué | Dónde en MongoDB |
|---|---|
| Ficha técnica + referencias a imágenes (un documento por máquina) | colección `maquinas` |
| Bytes de cada foto (GridFS) | colecciones `fs.files` y `fs.chunks` |

Las filas transaccionales (usuarios, carrito, alquileres) siguen en SQLite. Ambos
motores se enlazan por la **placa** de la máquina. El sitio sirve las fotos desde
`/media/maquinas/<slug>/<NN>.jpg`, leyéndolas de MongoDB.

### Configuración

Copia `.env.example` a `.env` (o define las variables de entorno, por ejemplo en
*Configuración → Variables de entorno* de Azure App Service):

```
MONGODB_URI=mongodb://localhost:27017        # o mongodb+srv://usuario:clave@cluster.mongodb.net
MONGODB_DB=msps
```

MongoDB local con Docker: `docker run -d --name msps-mongo -p 27017:27017 mongo:7`

Con MongoDB Atlas (gratis, 512 MB) basta pegar su cadena de conexión en `MONGODB_URI`
y permitir en Atlas la IP del servidor (*Network Access*). Las 22 fotos pesan ~6 MB.

Al arrancar, la app sube sola el catálogo y las fotos de `app/seed_data/imagenes_maquinas/`
(solo lo que falte o haya cambiado). Si MongoDB no responde, el sitio sigue funcionando
sin galería ni ficha y el motivo queda en el log.

### Agregar máquinas nuevas

1. Poner los datos en `app/catalogo_maquinas.py`.
2. `python -m tools.importar_imagenes --origen "carpeta/con/las/fotos"` (redimensiona y quita el GPS).
3. Reiniciar la app.

### Pruebas

```
pip install pytest mongomock
pytest                                   # MongoDB simulado en memoria
MSPS_TEST_MONGO_URI=mongodb://localhost:27017 pytest   # contra un MongoDB real
```

### Patrones y principios

- **Singleton:** `MongoConnection` (`app/documentos/store.py`).
- **Factory Method:** `FichaTecnicaFactory`, `crear_maquina_documentos_repositorio()`, `crear_imagenes_repositorio()`.
- **Builder + Director:** `MaquinaDocumentoBuilder` y `CatalogoDirector`.
- **SOLID:** repositorios con interfaces separadas de lectura y escritura (ISP), los controladores dependen de
  esas interfaces y no de pymongo (DIP), un tipo de ficha nuevo se agrega sin tocar código existente (OCP).
