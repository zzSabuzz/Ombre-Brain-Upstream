import asyncio
from pathlib import Path
from types import SimpleNamespace

from bucket_manager import BucketManager
from decay_engine import DecayEngine
from special_memory import SpecialMemoryService


def run(coro):
    return asyncio.run(coro)


def config(tmp_path: Path, *, auto_resolution: bool = False) -> dict:
    return {
        "buckets_dir": str(tmp_path / "buckets"),
        "matching": {"fuzzy_threshold": 50, "max_results": 10},
        "decay": {"lambda": 0.05, "threshold": 0.3, "emotion_weights": {}},
        "plan": {
            "auto_resolution": {
                "enabled": auto_resolution,
                "vector_threshold": 0.7,
                "confidence_threshold": 0.7,
                "top_k": 8,
            }
        },
    }


class FakeEmbedding:
    enabled = True

    def __init__(self):
        self.documents = {}
        self.results = []

    async def generate_and_store(self, bucket_id, content):
        self.documents[bucket_id] = content
        return True

    async def search_similar(self, query, top_k=10):
        return self.results[:top_k]


class FakeCompletions:
    def __init__(self):
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        message = SimpleNamespace(content='{"resolved": true, "confidence": 0.96, "reason": "explicit completion"}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeDehydrator:
    model = "fake"

    def __init__(self):
        self.completions = FakeCompletions()
        self.client = SimpleNamespace(chat=SimpleNamespace(completions=self.completions))


def test_letters_preserve_verbatim_search_filter_and_restart(tmp_path):
    cfg = config(tmp_path)
    manager = BucketManager(cfg)
    embeddings = FakeEmbedding()
    service = SpecialMemoryService(cfg, manager, embeddings)
    original = "  Dear future self,\n\nKeep every space.  \n"

    created = run(service.letter_write(
        original,
        author="ai",
        ai_name="Haven",
        date="2026-07-14",
        title="Migration",
    ))
    bucket_id = created["bucket_id"]
    bucket = run(manager.get(bucket_id))
    assert bucket["content"] == original
    assert bucket["metadata"]["author"] == "Haven"
    assert bucket["metadata"]["letter_date"] == "2026-07-14"
    assert "letters" in Path(bucket["path"]).parts
    assert embeddings.documents[bucket_id] == original

    lexical = run(service.letter_read(query="future self", author="Haven", date_from="2026-07-01", date_to="2026-07-31"))
    assert [item["id"] for item in lexical] == [bucket_id]
    assert lexical[0]["content"] == original

    restarted = SpecialMemoryService(cfg, BucketManager(cfg), embeddings)
    persisted = run(restarted.letter_read(author="Haven"))
    assert persisted[0]["content"] == original


def test_plan_dedup_lifecycle_weight_change_log_and_related_bucket(tmp_path):
    cfg = config(tmp_path)
    manager = BucketManager(cfg)
    service = SpecialMemoryService(cfg, manager, FakeEmbedding())
    related_id = run(manager.create("shipment done", domain=["project"]))

    first = run(service.plan(
        "Ship staging migration",
        weight=0.8,
        why_remembered="promised",
        related_bucket=related_id,
    ))
    duplicate = run(service.plan("Ship staging migration"))
    assert duplicate == {"bucket_id": first["bucket_id"], "deduplicated": True, "status": "active"}

    updated = run(service.update_plan(first["bucket_id"], status="resolved", weight=0.95, reason="test"))
    meta = updated["metadata"]
    assert meta["status"] == "resolved"
    assert meta["weight"] == 0.95
    assert len(meta["change_log"]) == 3
    assert run(manager.get(related_id))["metadata"]["resolved"] is True
    assert "plans" in Path(updated["path"]).parts


def test_i_is_self_anchor_isolated_and_persistent(tmp_path):
    cfg = config(tmp_path)
    manager = BucketManager(cfg)
    service = SpecialMemoryService(cfg, manager, FakeEmbedding())
    result = run(service.I("I prefer explicit uncertainty.", aspect="uncertainty"))
    bucket = run(manager.get(result["bucket_id"]))
    assert bucket["metadata"]["type"] == "i"
    assert bucket["metadata"]["self_anchor"] is True
    assert bucket["metadata"]["dont_surface"] is True
    assert "aspect:uncertainty" in bucket["metadata"]["tags"]
    assert "self" in Path(bucket["path"]).parts
    assert run(service.I(read=True, aspect="uncertainty", limit=1))[0]["id"] == result["bucket_id"]


def test_special_types_are_not_decayed_or_archived(tmp_path):
    cfg = config(tmp_path)
    manager = BucketManager(cfg)
    service = SpecialMemoryService(cfg, manager, FakeEmbedding())
    plan_id = run(service.plan("Never decay this"))["bucket_id"]
    letter_id = run(service.letter_write("verbatim", author="user"))["bucket_id"]
    i_id = run(service.I("A stable self observation", aspect="nature"))["bucket_id"]
    decay = DecayEngine(cfg, manager)

    for bucket_id in (plan_id, letter_id, i_id):
        bucket = run(manager.get(bucket_id))
        assert decay.calculate_score(bucket["metadata"]) == 50.0
        assert run(manager.archive(bucket_id)) is False
    result = run(decay.run_decay_cycle())
    assert result["checked"] == 0


def test_plan_resolution_flag_off_then_conservative_path_on(tmp_path):
    cfg = config(tmp_path, auto_resolution=False)
    manager = BucketManager(cfg)
    embedding = FakeEmbedding()
    dehydrator = FakeDehydrator()
    service = SpecialMemoryService(cfg, manager, embedding, dehydrator)
    plan_id = run(service.plan("Finish the migration"))["bucket_id"]
    embedding.results = [(plan_id, 0.91)]

    assert run(service.check_plan_resolution("event-off", "Migration finished")) == []
    assert dehydrator.completions.calls == 0
    assert run(manager.get(plan_id))["metadata"]["status"] == "active"

    cfg["plan"]["auto_resolution"]["enabled"] = True
    resolved = run(service.check_plan_resolution("event-on", "Migration finished and passed acceptance"))
    assert resolved == [plan_id]
    assert dehydrator.completions.calls == 1
    meta = run(manager.get(plan_id))["metadata"]
    assert meta["status"] == "resolved"
    assert meta["resolved_by"] == "event-on"


def test_backup_migration_knows_special_directories():
    from scripts.migrate_bucket_files import BUCKET_SUBDIRS

    assert {"plans", "letters", "self"}.issubset(BUCKET_SUBDIRS)
