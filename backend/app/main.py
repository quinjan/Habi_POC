from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base, create_sqlalchemy_engine, database_url_from_env
from backend.app.projects.router import router as project_workspaces_router
from backend.app.review.router import router as review_batches_router
from backend.app.sources.router import router as manual_source_entries_router
from backend.app.evidence import models as evidence_models  # noqa: F401
from backend.app.memory import models as memory_models  # noqa: F401
from backend.app.review import models as review_models  # noqa: F401
from backend.app.sources import models as sources_models  # noqa: F401
from backend.app.taxonomy import models as taxonomy_models  # noqa: F401


def create_app(
    *,
    database_url: str | None = None,
    create_tables: bool = True,
) -> FastAPI:
    app = FastAPI(title="Habi Per-Project Memory Lab API")
    engine = create_sqlalchemy_engine(database_url or database_url_from_env())
    app.state.engine = engine
    app.state.session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    if create_tables:
        Base.metadata.create_all(bind=engine)

    app.include_router(project_workspaces_router, prefix="/api/project-workspaces")
    app.include_router(manual_source_entries_router, prefix="/api/project-workspaces")
    app.include_router(review_batches_router, prefix="/api/project-workspaces")
    return app


app = create_app(create_tables=False)
