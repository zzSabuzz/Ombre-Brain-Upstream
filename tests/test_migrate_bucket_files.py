from pathlib import Path

from scripts.migrate_bucket_files import (
    apply_plan,
    build_bucket_plan,
    build_tombstone_plan,
)


def write_bucket(path: Path, bucket_id: str, *, body: str = "body", name: str = "Memory") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "---",
                f"id: {bucket_id}",
                f"name: {name}",
                "type: dynamic",
                "domain:",
                "  - project",
                "tags:",
                "  - migrated",
                "comments:",
                "  - id: c1",
                "    created: '2026-06-10T00:00:00+00:00'",
                "    author: Haven",
                "    kind: comment",
                "    content: kept comment",
                "comment_count: 1",
                "---",
                body,
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_plan_and_apply_copy_preserves_bucket_file(tmp_path: Path) -> None:
    source = tmp_path / "v1" / "buckets"
    target = tmp_path / "v2" / "buckets"
    source_file = source / "dynamic" / "project" / "Memory_abcd1234efgh.md"
    write_bucket(source_file, "abcd1234efgh", body="v1 body")

    items, summary = build_bucket_plan(source, target)

    assert summary["source_count"] == 1
    assert items[0].action == "copy"
    assert items[0].comment_count == 1

    result = apply_plan(items, backup_root=None)

    copied = target / "dynamic" / "project" / "Memory_abcd1234efgh.md"
    assert result["written_ids"] == ["abcd1234efgh"]
    assert copied.read_text(encoding="utf-8") == source_file.read_text(encoding="utf-8")


def test_same_id_conflict_requires_overwrite_and_backs_up(tmp_path: Path) -> None:
    source = tmp_path / "v1" / "buckets"
    target = tmp_path / "v2" / "buckets"
    source_file = source / "dynamic" / "project" / "Memory_abcd1234efgh.md"
    target_file = target / "dynamic" / "project" / "Old_abcd1234efgh.md"
    write_bucket(source_file, "abcd1234efgh", body="source body")
    write_bucket(target_file, "abcd1234efgh", body="target body")

    items, _ = build_bucket_plan(source, target)

    assert items[0].action == "conflict"
    assert items[0].reason == "target_id_exists"

    overwrite_items, _ = build_bucket_plan(source, target, overwrite=True)
    backup = tmp_path / "backup"
    result = apply_plan(overwrite_items, backup_root=backup)

    assert overwrite_items[0].action == "overwrite"
    assert result["written_ids"] == ["abcd1234efgh"]
    assert "source body" in target_file.read_text(encoding="utf-8")
    assert (backup / target_file.name).exists()


def test_tombstone_conflicts_with_live_target_bucket(tmp_path: Path) -> None:
    source = tmp_path / "v1" / "buckets"
    target = tmp_path / "v2" / "buckets"
    tombstone = source / ".tombstones" / "abcd1234efgh.json"
    tombstone.parent.mkdir(parents=True, exist_ok=True)
    tombstone.write_text('{"id":"abcd1234efgh","source":"deleted"}', encoding="utf-8")
    write_bucket(target / "dynamic" / "project" / "Memory_abcd1234efgh.md", "abcd1234efgh")

    items = build_tombstone_plan(source, target)

    assert items[0].action == "conflict"
    assert items[0].reason == "target_live_bucket_exists"
