from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from prompt_loader import UnknownPromptError
from routes.analysis import router as analysis_router
from routes.resume_review import router as resume_review_router
from routes.cover_letter import router as cover_letter_router
from routes.interview_prep import router as interview_prep_router

app = FastAPI(title="AI Job Application Copilot - AI Service")


@app.exception_handler(UnknownPromptError)
def unknown_prompt_handler(_request: Request, error: UnknownPromptError):
    return JSONResponse(status_code=400, content={"detail": {"message": str(error)}})


@app.get("/health")
def health():
    return {"ok": True}

app.include_router(analysis_router)
app.include_router(resume_review_router)
app.include_router(cover_letter_router)
app.include_router(interview_prep_router)