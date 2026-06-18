import pytest

from darkroom import DarkroomStore


def _store(tmp_path):
    return DarkroomStore(
        {
            "state_dir": str(tmp_path / "state"),
            "buckets_dir": str(tmp_path / "buckets"),
        }
    )


def test_darkroom_enter_does_not_echo_note(tmp_path):
    store = _store(tmp_path)
    secret = "这是一句还没显影的暗房正文"

    result = store.enter(secret, completeness=0.4, mood="quiet", tags="暗房,未完成", lock_for="6小时")

    assert result["status"] == "entered"
    assert result["visible_note"] == "AI 进入了暗房。"
    assert secret not in str(result)
    assert result["completeness"] == {"previous": None, "current": 0.4}
    assert result["tags"] == ["暗房", "未完成"]
    assert result["locked_until"]


def test_darkroom_door_uses_configured_ai_name(tmp_path):
    store = DarkroomStore(
        {
            "state_dir": str(tmp_path / "state"),
            "buckets_dir": str(tmp_path / "buckets"),
            "identity": {"ai_name": "Ombre"},
        }
    )

    result = store.enter("名字也不该泄正文", completeness=0.3)
    status = store.status()

    assert result["visible_note"] == "Ombre 进入了暗房。"
    assert "钥匙只给 Ombre" in status["door"]
    assert "Haven" not in result["visible_note"]
    assert "Haven" not in status["door"]


def test_darkroom_status_is_door_only(tmp_path):
    store = _store(tmp_path)
    secret = "不能出现在门口状态里的句子"
    first = store.enter(secret, completeness=0.2)
    second = store.enter("第二条也不该回显", completeness=0.6, mood="developing")

    status = store.status()

    assert status["status"] == "ok"
    assert status["count"] == 1
    assert first["room_id"] == second["room_id"]
    assert second["revision"] == 2
    assert status["last_entry_id"] == second["entry_id"]
    assert status["last_room_id"] == second["room_id"]
    assert status["previous_completeness"] == 0.2
    assert status["last_completeness"] == 0.6
    assert first["entry_id"] != second["entry_id"]
    assert secret not in str(status)


def test_darkroom_continue_anchor_stays_private(tmp_path):
    store = _store(tmp_path)
    old_secret = "上一条暗房里不该出门的句子"
    store.enter(old_secret, completeness=0.2)

    result = store.enter("新的暗房正文", mode="continue", completeness=0.5)

    assert result["mode"] == "continue"
    assert result["continuation_anchor_entries"] == 1
    assert old_secret not in str(result)
    assert old_secret not in str(store.status())


def test_darkroom_continue_context_returns_recent_active_notes(tmp_path):
    store = _store(tmp_path)
    first_secret = "第一条 active 暗房正文"
    second_secret = "第二条 active 暗房正文"
    archived_secret = "归档正文不该进续写上下文"
    store.enter(first_secret, completeness=0.2)
    store.enter(archived_secret, completeness=0.9, visibility="archived", new_room=True)
    store.enter(second_secret, completeness=0.5)

    context = store.continue_context(limit=3)

    assert context["status"] == "ok"
    assert context["count"] == 1
    assert context["entries"][0]["content"] == second_secret
    assert context["entries"][0]["revision"] == 2
    assert archived_secret not in str(context)


def test_darkroom_new_room_creates_separate_active_draft(tmp_path):
    store = _store(tmp_path)
    first = store.enter("第一间房", completeness=0.4)
    second = store.enter("第二间房", completeness=0.2, new_room=True)

    status = store.status()
    context = store.continue_context()

    assert first["room_id"] != second["room_id"]
    assert second["revision"] == 1
    assert status["count"] == 2
    assert status["last_room_id"] == second["room_id"]
    assert context["entries"][0]["room_id"] == second["room_id"]
    assert context["entries"][0]["content"] == "第二间房"


def test_darkroom_single_mode_has_no_continuation_anchor(tmp_path):
    store = _store(tmp_path)
    store.enter("上一条暗房正文", completeness=0.2)

    result = store.enter("单独写一条", mode="single", completeness=0.5)

    assert result["mode"] == "single"
    assert result["continuation_anchor_entries"] == 0


def test_darkroom_release_explicitly_returns_content(tmp_path):
    store = _store(tmp_path)
    secret = "这句显影以后可以被带出来"
    store.enter(secret, completeness=1.0, tags="ready")

    released = store.release("latest", reason="小雨 asked")

    assert released["status"] == "released"
    assert released["content"] == secret
    assert released["tags"] == ["ready"]
    assert store.status()["released_count"] == 1


def test_darkroom_view_returns_content_without_release_count(tmp_path):
    store = _store(tmp_path)
    secret = "这句可以只读查看"
    store.enter(secret, completeness=1.0, tags="ready")

    viewed = store.view("latest")

    assert viewed["status"] == "visible"
    assert viewed["content"] == secret
    assert viewed["tags"] == ["ready"]
    assert store.status()["released_count"] == 0


def test_darkroom_view_returns_all_room_revisions(tmp_path):
    store = _store(tmp_path)
    first = "第一版暗房"
    second = "第二版暗房"
    store.enter(first, completeness=0.4)
    result = store.enter(second, completeness=1.0)

    viewed = store.view(result["room_id"])

    assert viewed["status"] == "visible"
    assert viewed["content"] == second
    assert [entry["content"] for entry in viewed["entries"]] == [first, second]
    assert [entry["revision"] for entry in viewed["entries"]] == [1, 2]


def test_darkroom_view_blocks_incomplete_entry(tmp_path):
    store = _store(tmp_path)
    secret = "完整度不到 1 不能查看"
    store.enter(secret, completeness=0.9, tags="draft")

    viewed = store.view("latest")
    released = store.release("latest", reason="too early")

    assert viewed["status"] == "not_ready"
    assert viewed["completeness"] == 0.9
    assert "content" not in viewed
    assert secret not in str(viewed)
    assert released["status"] == "not_ready"
    assert secret not in str(released)
    assert store.status()["released_count"] == 0


def test_darkroom_view_respects_lock_for(tmp_path):
    store = _store(tmp_path)
    secret = "锁门期间不能出现在 view 里"
    store.enter(secret, completeness=1.0, lock_for="1d")

    viewed = store.view("latest")
    released = store.release("latest", reason="too early")

    assert viewed["status"] == "locked"
    assert "unlock_at" in viewed
    assert "content" not in viewed
    assert secret not in str(viewed)
    assert released["status"] == "locked"
    assert secret not in str(released)
    assert store.status()["released_count"] == 0


def test_darkroom_view_allows_expired_lock(tmp_path):
    store = _store(tmp_path)
    secret = "过期以后可以查看"
    legacy = {
        "id": "dr_expired_lock",
        "created_at": "2000-01-01T00:00:00+08:00",
        "note": secret,
        "mode": "continue",
        "completeness": 1.0,
        "previous_entry_id": "",
        "previous_completeness": None,
        "continuation_anchor": {},
        "mood": "old",
        "tags": ["ready"],
        "source": "test",
        "visibility": "active",
        "locked_until": "2000-01-02T00:00:00+08:00",
    }
    store._append_jsonl_unlocked(store.entries_path, legacy)

    viewed = store.view("latest")

    assert viewed["status"] == "visible"
    assert viewed["content"] == secret


def test_darkroom_status_defaults_to_active_entries(tmp_path):
    store = _store(tmp_path)
    active = store.enter("active door note", completeness=0.3)
    archived = store.enter("archived door note", completeness=0.9, visibility="archived", new_room=True)
    retracted = store.enter("retracted door note", completeness=1.0, visibility="retracted", new_room=True)

    status = store.status()

    assert active["visibility"] == "active"
    assert archived["visibility"] == "archived"
    assert retracted["visibility"] == "retracted"
    assert status["count"] == 1
    assert status["last_entry_id"] == active["entry_id"]
    assert status["last_completeness"] == 0.3
    assert "archived door note" not in str(status)
    assert "retracted door note" not in str(status)


def test_darkroom_release_latest_skips_archived_and_retracted(tmp_path):
    store = _store(tmp_path)
    active_secret = "active release note"
    store.enter(active_secret, completeness=1.0, tags="ready")
    store.enter("archived release note", completeness=1.0, visibility="archived", new_room=True)
    store.enter("retracted release note", completeness=1.0, visibility="retracted", new_room=True)

    released = store.release("latest", reason="release latest active")

    assert released["status"] == "released"
    assert released["content"] == active_secret
    assert store.status()["released_count"] == 1


def test_darkroom_view_blocks_legacy_entry_without_completeness(tmp_path):
    store = _store(tmp_path)
    legacy = {
        "id": "dr_legacy_no_completeness",
        "created_at": "2026-06-10T12:00:00+08:00",
        "note": "legacy note without completeness",
        "mode": "continue",
        "previous_entry_id": "",
        "previous_completeness": None,
        "continuation_anchor": {},
        "mood": "old",
        "tags": ["legacy"],
        "source": "test",
        "visibility": "active",
    }
    store._append_jsonl_unlocked(store.entries_path, legacy)

    viewed = store.view("latest")

    assert viewed["status"] == "not_ready"
    assert "content" not in viewed
    assert "legacy note without completeness" not in str(viewed)


def test_darkroom_legacy_entries_without_visibility_are_active(tmp_path):
    store = _store(tmp_path)
    legacy = {
        "id": "dr_legacy",
        "created_at": "2026-06-10T12:00:00+08:00",
        "note": "legacy active note",
        "mode": "continue",
        "completeness": 1.0,
        "previous_entry_id": "",
        "previous_completeness": None,
        "continuation_anchor": {},
        "mood": "old",
        "tags": ["legacy"],
        "source": "test",
    }
    store._append_jsonl_unlocked(store.entries_path, legacy)

    status = store.status()
    released = store.release("latest", reason="legacy active")

    assert status["count"] == 1
    assert status["last_entry_id"] == "dr_legacy"
    assert released["content"] == "legacy active note"


def test_darkroom_rejects_empty_note(tmp_path):
    store = _store(tmp_path)

    with pytest.raises(ValueError, match="note is empty"):
        store.enter("  ")
