import json
from pathlib import Path

from app.scripts.export_openapi import export_openapi


def test_export_writes_stable_json(tmp_path: Path) -> None:
    first, second = tmp_path / "a.json", tmp_path / "b.json"

    export_openapi(first)
    export_openapi(second)

    assert first.read_text() == second.read_text()
    assert first.read_text().endswith("\n")
    spec = json.loads(first.read_text())
    assert "/api/v1/health" in spec["paths"]


def test_operation_ids_are_route_function_names(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"

    export_openapi(target)

    spec = json.loads(target.read_text())
    assert spec["paths"]["/api/v1/me"]["get"]["operationId"] == "get_me"
    assert spec["paths"]["/api/v1/settings"]["patch"]["operationId"] == "update_my_settings"
