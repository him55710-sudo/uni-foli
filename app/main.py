from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
import uvicorn

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from db.session import initialize_database, session_scope
from services.admissions.auth_service import auth_service
from services.admissions.catalog_service import catalog_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    configure_logging()
    if settings.database_auto_create_tables:
        initialize_database()
        with session_scope() as session:
            catalog_service.bootstrap_reference_data(session)
            auth_service.bootstrap_defaults(session)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        debug=settings.app_debug,
        lifespan=lifespan,
        description=(
            "Source-grounded admissions intelligence backend for Korean admissions guidance. "
            "Supports traceable ingestion, evidence-aware parsing, and student-file analysis scaffolding."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    def home() -> str:
        return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Polio Admissions Backend</title>
    <style>
      body { font-family: "Segoe UI", "Noto Sans KR", sans-serif; margin: 0; background: #f5f7fb; color: #0f172a; }
      main { max-width: 960px; margin: 0 auto; padding: 72px 24px; }
      .card { background: white; border-radius: 24px; padding: 32px; border: 1px solid #d8e0ea; box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08); }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 24px; }
      a { display: block; text-decoration: none; color: inherit; background: #f8fafc; border: 1px solid #d8e0ea; border-radius: 16px; padding: 18px; }
      code { display: inline-block; margin-top: 8px; color: #155e75; background: #e0f2fe; padding: 4px 8px; border-radius: 8px; }
    </style>
  </head>
  <body>
    <main>
      <section class="card">
        <h1>Polio admissions intelligence backend</h1>
        <p>Official-source ingestion, provenance-preserving claims, and explainable student-file analysis.</p>
        <div class="grid">
          <a href="/docs"><strong>Open API Docs</strong><code>/docs</code></a>
          <a href="/api/v1/health"><strong>Health</strong><code>/api/v1/health</code></a>
          <a href="/api/v1/sources"><strong>Sources</strong><code>/api/v1/sources</code></a>
          <a href="/api/v1/student-files"><strong>Student Files</strong><code>/api/v1/student-files</code></a>
        </div>
      </section>
    </main>
  </body>
</html>
        """.strip()

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(status_code=204)

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port, reload=settings.app_debug)


if __name__ == "__main__":
    run()
