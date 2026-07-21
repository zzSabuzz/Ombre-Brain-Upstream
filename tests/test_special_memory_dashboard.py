from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_exposes_special_memory_views_and_actions():
    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")

    for tab, view, loader in (
        ("letters", "letters-view", "loadLetters"),
        ("self-knowledge", "self-knowledge-view", "loadSelfKnowledge"),
        ("plans", "plans-view", "loadPlans"),
    ):
        assert f'data-tab="{tab}"' in html
        assert f'id="{view}"' in html
        assert f"function {loader}(" in html

    assert "/api/special-memory/letter" in html
    assert "/api/special-memory/i" in html
    assert "/api/special-memory/plan" in html

    ids = [value for value in re.findall(r'\bid="([^"]+)"', html) if "+" not in value]
    assert len(ids) == len(set(ids)), "dashboard element IDs must remain unique"


def test_dashboard_api_routes_keep_special_memory_isolated():
    source = (ROOT / "server.py").read_text(encoding="utf-8")

    assert '@mcp.custom_route("/api/special-memory", methods=["GET"])' in source
    assert '@mcp.custom_route("/api/special-memory/letter", methods=["POST"])' in source
    assert '@mcp.custom_route("/api/special-memory/i", methods=["POST"])' in source
    assert '@mcp.custom_route("/api/special-memory/plan", methods=["POST"])' in source
    assert '@mcp.custom_route("/api/special-memory/plan/{plan_id}", methods=["PATCH"])' in source

    route_block = source[source.index("async def api_special_memory_list"):source.index('@mcp.custom_route("/api/reminders"')]
    assert "special_memory.letter_read" in route_block
    assert "special_memory.I" in route_block
    assert "special_memory.letter_write" in route_block
    assert "special_memory.plan" in route_block
    assert "special_memory.update_plan" in route_block
    assert "bucket_mgr.create" not in route_block
