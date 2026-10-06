"""
Capa de documentos (base de datos NO relacional, MongoDB) de MSPS.

Guarda, por cada máquina, un documento autocontenido con su ficha técnica y
la referencia a sus imágenes; los bytes de las fotos viven en GridFS, dentro
de la misma base MongoDB. Convive con la base relacional (SQLite): ésta
conserva lo transaccional (alquileres, carrito, facturas) y esta capa
conserva el contenido descriptivo y multimedia, que es jerárquico y cambia
de forma según el tipo de equipo.

Contenido:
- store.py             -> Singleton de la conexión a MongoDB.
- fichas.py            -> Factory Method de fichas técnicas por tipo de equipo.
- maquina_documento.py -> Documento de máquina + Builder que lo construye.
"""
