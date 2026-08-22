from pathlib import Path


def test_health_route_exists() -> None:
    main_py = Path(__file__).resolve().parents[1] / "main.py"
    content = main_py.read_text(encoding="utf-8")
    assert '@app.get("/health")' in content
