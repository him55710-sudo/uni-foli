from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
import uvicorn

from polio_api.api.router import api_router
from polio_api.core.config import get_settings
from polio_api.core.database import initialize_database
from polio_shared.paths import ensure_app_directories


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    ensure_app_directories()
    if settings.database_auto_create_tables:
        initialize_database()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.app_debug,
        lifespan=lifespan,
        description=(
            "Beginner-friendly backend skeleton for polio. "
            "Create projects, upload files, write drafts, and queue render jobs."
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
    def home_page() -> str:
        return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>polio Backend</title>
    <style>
      :root {
        color-scheme: light;
        --bg: #f3f7fb;
        --card: #ffffff;
        --ink: #0f172a;
        --muted: #475569;
        --line: #dbe4ee;
        --accent: #0f766e;
        --accent-strong: #115e59;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        font-family: "Segoe UI", "Noto Sans KR", sans-serif;
        background:
          radial-gradient(circle at top right, rgba(15, 118, 110, 0.12), transparent 28%),
          linear-gradient(180deg, #f8fbfd 0%, var(--bg) 100%);
        color: var(--ink);
      }
      main {
        max-width: 920px;
        margin: 0 auto;
        padding: 72px 24px;
      }
      .hero {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 28px;
        padding: 36px;
        box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
      }
      .eyebrow {
        display: inline-flex;
        padding: 8px 12px;
        border-radius: 999px;
        background: rgba(15, 118, 110, 0.1);
        color: var(--accent-strong);
        font-size: 14px;
        font-weight: 700;
      }
      h1 {
        margin: 16px 0 12px;
        font-size: clamp(32px, 5vw, 54px);
        line-height: 1.05;
      }
      p {
        margin: 0;
        color: var(--muted);
        font-size: 18px;
        line-height: 1.7;
      }
      .actions, .grid {
        display: grid;
        gap: 16px;
      }
      .actions {
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        margin-top: 28px;
      }
      .grid {
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        margin-top: 28px;
      }
      a.card, .info {
        display: block;
        text-decoration: none;
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 22px;
        padding: 20px;
        transition: transform 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
      }
      a.card:hover, a.card:focus-visible {
        transform: translateY(-2px);
        border-color: rgba(15, 118, 110, 0.4);
        box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
      }
      strong {
        display: block;
        margin-bottom: 8px;
        color: var(--ink);
        font-size: 18px;
      }
      code {
        display: inline-block;
        margin-top: 8px;
        padding: 4px 8px;
        border-radius: 8px;
        background: #e2f3f1;
        color: #134e4a;
        font-size: 13px;
      }
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <span class="eyebrow">polio backend</span>
        <h1>Upload, parse, draft, and render from one backend.</h1>
        <p>
          This local service powers the beginner-friendly backend blueprint for polio.
          Start from the API docs, confirm health, and inspect available render formats.
        </p>
        <div class="actions">
          <a class="card" href="/docs">
            <strong>Open API Docs</strong>
            Browse and execute every route from Swagger UI.
            <code>/docs</code>
          </a>
          <a class="card" href="/api/v1/health">
            <strong>Check Server Health</strong>
            Confirm the backend is responding correctly.
            <code>/api/v1/health</code>
          </a>
          <a class="card" href="/api/v1/render-jobs/formats">
            <strong>See Render Formats</strong>
            Verify which export formats are available now.
            <code>/api/v1/render-jobs/formats</code>
          </a>
        </div>
      </section>
      <section class="grid" aria-label="backend highlights">
        <div class="info">
          <strong>Automatic Ingest</strong>
          PDF, TXT, and MD uploads can be parsed into documents and chunks immediately.
        </div>
        <div class="info">
          <strong>Selected Rendering</strong>
          Users choose one output format per job: PDF, PPTX, or HWPX.
        </div>
        <div class="info">
          <strong>Safe Local Setup</strong>
          SQLite works out of the box, and PostgreSQL plus pgvector is ready when needed.
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
    uvicorn.run(
        "polio_api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )


if __name__ == "__main__":
    run()
