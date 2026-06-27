import argparse

from sqlalchemy.orm import sessionmaker

from backend.app.database import create_sqlalchemy_engine, database_url_from_env
from backend.app.processing.worker import run_loop, run_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()

    engine = create_sqlalchemy_engine(database_url_from_env())
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    if args.loop:
        run_loop(session_factory)
        return 0
    run_once(session_factory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
