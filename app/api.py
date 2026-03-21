from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Sentinel AIP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True, "status": "ok"}

@app.get("/cases/list")
def list_cases(limit: int = 50):
    return {"cases": [], "count": 0, "status": "fallback"}

@app.get("/")
def root():
    return {"service": "qss-backend", "status": "running"}
