from fastapi import FastAPI
from routes.analysis import router as analysis_router

app = FastAPI(title="AI Job Application Copilot - AI Service")

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(analysis_router)