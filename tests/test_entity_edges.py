from entity_edges import EntityEdgeStore, entity_query_hints, extract_entity_edges_from_bucket


def test_extract_entity_edges_from_bucket_uses_configured_names(test_config):
    identity = {
        "ai_name": "Haven",
        "user_name": "Xiaoyu",
        "user_display_name": "小雨",
        "user_aliases": ["宝宝"],
    }
    bucket = {
        "id": "bucket-a",
        "metadata": {
            "name": "暗色故事偏好",
            "tags": ["偏好", "故事"],
            "domain": ["relationship"],
        },
        "content": "小雨喜欢暗色故事，也讨厌模板安慰。Haven参与Ombre-Brain记忆系统开发。",
    }

    edges = extract_entity_edges_from_bucket(bucket, identity)
    rows = {(edge["subject"], edge["relation"], edge["object_text"]) for edge in edges}

    assert ("小雨", "likes", "暗色故事") in rows
    assert ("小雨", "dislikes", "模板安慰") in rows
    assert ("Haven", "participates_in", "Ombre-Brain记忆系统开发") in rows

    store = EntityEdgeStore(test_config)
    saved = store.replace_bucket_edges("bucket-a", edges)
    assert len(saved) == len(edges)

    matches = store.match_query("我喜欢的故事", identity, bucket_ids={"bucket-a"})
    assert matches["bucket-a"]["relation"] == "likes"
    assert matches["bucket-a"]["score"] > 0.6


def test_entity_query_hints_map_pronouns_to_configured_subjects():
    identity = {
        "ai_name": "Echo",
        "user_name": "Mira",
        "user_display_name": "米拉",
        "user_aliases": ["亲爱的"],
    }

    like_hint = entity_query_hints("我喜欢的颜色", identity)[0]
    participation_hint = entity_query_hints("你参与的项目", identity)[0]
    shared_hint = entity_query_hints("我们之前的暗号", identity)[0]

    assert like_hint["subject"] == "米拉"
    assert "likes" in like_hint["relations"]
    assert participation_hint["subject"] == "Echo"
    assert "participates_in" in participation_hint["relations"]
    assert shared_hint["subject"] == "米拉+Echo"
    assert "shared_anchor" in shared_hint["relations"]


def test_extract_entity_edges_does_not_treat_nominal_writing_window_as_participation(test_config):
    identity = {
        "ai_name": "Haven",
        "user_name": "Xiaoyu",
        "user_display_name": "小雨",
        "user_aliases": ["宝宝"],
    }
    bucket = {
        "id": "poem-window",
        "metadata": {
            "name": "写诗分支窗口",
            "tags": ["小雨", "Haven", "写诗", "分支窗口"],
            "domain": ["核心"],
        },
        "content": "小雨和Haven有一个写诗分支窗口。那里两人用问答接诗，这个分支代表连续性和记忆接力的约定。",
    }

    edges = extract_entity_edges_from_bucket(bucket, identity)

    assert not any(edge["relation"] == "participates_in" for edge in edges)
    assert any(edge["relation"] == "shared_anchor" for edge in edges)
