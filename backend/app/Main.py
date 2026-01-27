from fastapi import FastAPI

app = FastAPI(title="Smart Irrigation API")

@app.get("/")
def root():
    return {"status": "API funcionando 🚀"}