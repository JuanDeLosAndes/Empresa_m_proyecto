from fastapi import FastAPI
# 1. Crear la instancia de FastAPI (ESTO ES OBLIGATORIO)
app = FastAPI()
# 2. Definir al menos un endpoint (ruta) (ESTO ES OBLIGATORIO)
@app.get("/")
def home():
 return {"mensaje": "Mi API esta funcionando"}
# 3. Si quieren ma s endpoints, los agregan así :
@app.get("/eventos")
def listar_eventos():
 return {"eventos": ["CONIITI 2024", "Taller React", "Charla IA"]}