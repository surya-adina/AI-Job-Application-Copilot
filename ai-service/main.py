from fastapi import FastAPI
from routes.analysis import router as analysis_router
from routes.resume_review import router as resume_review_router

app = FastAPI(title="AI Job Application Copilot - AI Service")

@app.get("/health")
def health():
    return {"ok": True}

app.include_router(analysis_router)
app.include_router(resume_review_router)