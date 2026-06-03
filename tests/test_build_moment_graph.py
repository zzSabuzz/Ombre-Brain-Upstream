import asyncio
from argparse import Namespace

from bucket_manager import BucketManager
from memory_moments import MemoryMomentStore
from scripts import build_moment_graph


def _moment(
    bucket_id: str,
    text: str,
    *,
    tags: list[str] | None = None,
    domain: list[str] | None = None,
    facets: dict[str, float] | None = None,
) -> dict:
    return {
        "moment_id": f"{bucket_id}:m1",
        "bucket_id": bucket_id,
        "section": "body",
        "text": text,
        "metadata": {
            "bucket_name": bucket_id,
            "bucket_tags": tags or [],
            "bucket_domain": domain or [],
            "annotation_summary": text,
            "annotation_facets": facets or {},
        },
    }


def test_build_cross_bucket_edges_prefers_shared_terms_and_facets():
    moments = [
        _moment(
            "blue-seed",
            "FF14 蓝色偏好是小雨稳定的界面线索。",
            tags=["ff14", "blue_preference"],
            domain=["game"],
            facets={"profile_preference": 0.8},
        ),
        _moment(
            "blue-context",
            "FF14 蓝色界面后续：雨天安静主题继续用蓝色。",
            tags=["ff14", "blue_preference"],
            domain=["game"],
            facets={"profile_preference": 0.7},
        ),
        _moment(
            "hardware",
            "ESP32 触摸模块和 MPR121 铜箔输入。",
            tags=["hardware_protocol"],
            domain=["hardware"],
            facets={"hardware_protocol": 0.8},
        ),
    ]

    edges = build_moment_graph.build_cross_bucket_edges(
        moments,
        min_score=0.58,
        max_edges_per_moment=2,
    )
    pairs = {(edge["source"], edge["target"]) for edge in edges}

    assert ("blue-seed:m1", "blue-context:m1") in pairs
    assert ("blue-context:m1", "blue-seed:m1") in pairs
    assert not any("hardware" in edge["source"] or "hardware" in edge["target"] for edge in edges)
    assert all(edge["reason"].startswith("local_graph:") for edge in edges)


def test_replace_generated_edges_preserves_bucket_context_edges(test_config):
    store = MemoryMomentStore(test_config)
    store.upsert_bucket(
        {
            "id": "bucket-a",
            "content": "## context\n背景。\n\n## original\n正文。",
            "metadata": {"id": "bucket-a", "name": "bucket-a", "type": "dynamic"},
        }
    )
    same_bucket_edges = store.list_edges("bucket-a")
    generated = {
        "source": "bucket-a:m1",
        "target": "bucket-b:m1",
        "bucket_id": "bucket-a",
        "relation_type": "supports",
        "confidence": 0.7,
        "reason": "local_graph: test generated edge",
        "created_at": "2026-06-01T00:00:00+00:00",
    }

    assert same_bucket_edges
    assert store.replace_generated_edges([generated]) == 1
    assert any(edge["reason"].startswith("local_graph:") for edge in store.list_edges())

    assert store.replace_generated_edges([]) == 0
    remaining = store.list_edges()
    assert same_bucket_edges[0]["reason"] in {edge["reason"] for edge in remaining}
    assert not any(edge["reason"].startswith("local_graph:") for edge in remaining)


def test_run_once_writes_edges_and_incremental_idle(monkeypatch, test_config, tmp_path):
    bucket_mgr = BucketManager(test_config)
    asyncio.run(
        bucket_mgr.create(
            content="FF14 蓝色偏好是小雨稳定的界面线索。",
            tags=["ff14", "blue_preference"],
            domain=["game"],
            name="蓝色偏好",
        )
    )
    asyncio.run(
        bucket_mgr.create(
            content="FF14 蓝色界面后续：雨天安静主题继续用蓝色。",
            tags=["ff14", "blue_preference"],
            domain=["game"],
            name="蓝色后续",
        )
    )
    monkeypatch.setattr(build_moment_graph, "load_config", lambda: test_config)
    args = Namespace(
        incremental=False,
        write=True,
        force=False,
        state_file=str(tmp_path / "moment-worker.json"),
        min_score=0.58,
        max_edges_per_moment=2,
        max_moments=100,
    )

    result = asyncio.run(build_moment_graph.run_once(args))

    assert result["status"] == "ok"
    assert result["dry_run"] is False
    assert result["written_edge_count"] > 0
    assert result["indexed"]["buckets"] == 2

    idle_args = Namespace(**{**vars(args), "incremental": True})
    idle = asyncio.run(build_moment_graph.run_once(idle_args))

    assert idle["status"] == "idle"
    assert idle["changed_bucket_count"] == 0
