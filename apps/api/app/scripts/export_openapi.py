"""Write the OpenAPI schema to a file: python -m app.scripts.export_openapi <path>.

Builds the app with fake providers and without running the lifespan, so no database or
external service is needed.
"""

import json
import sys
from pathlib import Path

from app.core.config import Settings
from app.main import create_app


def export_openapi(path: Path) -> None:
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url="postgresql+asyncpg://unused/unused",
        llm_provider="fake",
        stt_provider="fake",
        tts_provider="fake",
        pronunciation_provider="fake",
    )
    spec = create_app(settings).openapi()
    path.write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.scripts.export_openapi <output-path>")
    export_openapi(Path(sys.argv[1]))
