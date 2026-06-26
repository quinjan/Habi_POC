from fastapi import FastAPI
from sqlalchemy.orm import sessionmaker

from backend.app.database import Base, create_sqlalchemy_engine, database_url_from_env
from backend.app.projects.router import router as project_workspaces_router


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
    return app


app = create_app(create_tables=False)
