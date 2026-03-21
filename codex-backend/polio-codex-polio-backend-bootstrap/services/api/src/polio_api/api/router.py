from fastapi import APIRouter

from polio_api.api.routes import auth, diagnosis, documents, drafts, health, projects, render_jobs, research, uploads, users

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(drafts.chat_router, prefix="/drafts", tags=["chat"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(uploads.router, prefix="/projects", tags=["uploads"])
api_router.include_router(documents.router, prefix="/projects", tags=["documents"])
api_router.include_router(drafts.router, prefix="/projects", tags=["drafts"])
api_router.include_router(diagnosis.router, prefix="/projects", tags=["diagnosis"])
api_router.include_router(render_jobs.router, tags=["render-jobs"])
