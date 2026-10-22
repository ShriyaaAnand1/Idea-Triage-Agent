
from fastapi import FastAPI

from routes.user import user_router
from routes.reviewer import reviewer_router
from services.lifecycle import lifespan
from logger.logging import logger

app = FastAPI(
    title="Idea Triage Agent API",
    version="2.2.0",
    lifespan=lifespan,
)

app.include_router(user_router)
app.include_router(reviewer_router)


@app.get("/")
def home():
    return {
        "message": "Idea Triage Agent API is running",
        "status": "healthy",
    }
