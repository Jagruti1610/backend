from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.database import engine, Base
from .api.v1.endpoints import auth, documents
import os

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Legal Document Summarizer API", version="1.0")

# ✅ CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://ai-legal-assistant-mauve.vercel.app",
        "https://ai-legal-assistant-omega.vercel.app",
        "https://backend-pro-mm41.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")

@app.get("/")
def root():
    return {"message": "Legal Summarizer API is running perfectly!"}

# ✅ For Render deployment
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)