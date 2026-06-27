import argparse

from sqlalchemy.orm import sessionmaker

from backend.app.database import create_sqlalchemy_engine, database_url_from_env
from backend.app.processing.openai_provider import (
    OpenAiExtractionProvider,
    OpenAiProviderConfig,
)
from backend.app.processing.worker import run_loop, run_once


def create_openai_provider_from_env() -> OpenAiExtractionProvider:
    return OpenAiExtractionProvider(OpenAiProviderConfig.from_env())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    engine = create_sqlalchemy_engine(database_url_from_env())
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    if args.loop:
        run_loop(session_factory, ai_provider_factory=create_openai_provider_from_env)
        return 0
    run_once(session_factory, ai_provider_factory=create_openai_provider_from_env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
