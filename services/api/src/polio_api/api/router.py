from fastapi import APIRouter

from polio_api.api.routes import documents, drafts, health, projects, render_jobs, uploads

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(uploads.router, prefix="/projects", tags=["uploads"])
api_router.include_router(documents.router, prefix="/projects", tags=["documents"])
api_router.include_router(drafts.router, prefix="/projects", tags=["drafts"])
api_router.include_router(render_jobs.router, tags=["render-jobs"])
