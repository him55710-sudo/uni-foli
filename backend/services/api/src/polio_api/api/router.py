from fastapi import APIRouter

from polio_api.api.routes import (
    answers,
    auth,
    blueprints,
    diagnosis,
    documents,
    drafts,
    global_documents,
    health,
    jobs,
    projects,
    quests,
    render_jobs,
    research,
    uploads,
    users,
    workshops,
    assets,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(answers.router, prefix="/projects", tags=["answers"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(drafts.chat_router, prefix="/drafts", tags=["chat"])
api_router.include_router(research.router, prefix="/research", tags=["research"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(uploads.router, prefix="/projects", tags=["uploads"])
api_router.include_router(documents.router, prefix="/projects", tags=["documents"])
api_router.include_router(global_documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(drafts.router, prefix="/projects", tags=["drafts"])
api_router.include_router(diagnosis.router, prefix="/diagnosis", tags=["diagnosis"])
api_router.include_router(blueprints.router, prefix="/blueprints", tags=["blueprints"])
api_router.include_router(quests.router, prefix="/quests", tags=["quests"])
api_router.include_router(workshops.router, prefix="/workshops", tags=["workshops"])
api_router.include_router(render_jobs.router, tags=["render-jobs"])
api_router.include_router(assets.router, prefix="/assets", tags=["assets"])
