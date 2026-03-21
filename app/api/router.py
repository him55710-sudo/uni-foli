from fastapi import APIRouter

from app.api.routes import admin, analysis_runs, auth, chat, claims, crawl, documents, health, ingestion_jobs, retrieval, sources, student_files


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(crawl.router, prefix="/crawl", tags=["crawl"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(claims.router, prefix="/claims", tags=["claims"])
api_router.include_router(ingestion_jobs.router, prefix="/ingestion/jobs", tags=["ingestion-jobs"])
api_router.include_router(retrieval.router, prefix="/retrieval", tags=["retrieval"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(student_files.router, prefix="/student-files", tags=["student-files"])
api_router.include_router(analysis_runs.router, prefix="/analysis/runs", tags=["analysis-runs"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
