import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.main import create_app


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("backend/openapi.json")
    app = create_app(database_url="sqlite+pysqlite:///:memory:", create_tables=False)
    output_path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
