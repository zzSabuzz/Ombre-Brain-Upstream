import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from identity import identity_names
from utils import strip_wikilinks


ENTITY_RELATIONS = {
    "likes",
    "dislikes",
    "prefers",
    "fears",
    "boundary",
    "habit",
    "participates_in",
    "shared_anchor",
}

USER_RELATION_SPECS = (
    ("dislikes", r"(?:很|最|一直|特别|也|更)?不喜欢\s*([^。；;，,\n]{1,40})"),
    ("dislikes", r"(?:很|最|一直|特别|也|更)?讨厌\s*([^。；;，,\n]{1,40})"),
    ("dislikes", r"(?:很|最|一直|特别|也|更)?厌恶\s*([^。；;，,\n]{1,40})"),
    ("likes", r"(?:很|最|一直|特别|也|更|偏)?喜欢\s*([^。；;，,\n]{1,40})"),
    ("prefers", r"偏好\s*([^。；;，,\n]{1,40})"),
    ("fears", r"(?:很|最|一直|特别|也|更)?害怕\s*([^。；;，,\n]{1,40})"),
    ("boundary", r"(?:的)?雷点是\s*([^。；;，,\n]{1,40})"),
    ("habit", r"(?:有个)?习惯是\s*([^。；;，,\n]{1,40})"),
)

AI_PARTICIPATION_TAIL = (
    r".{0,18}(?:参与|一起|共同|协作|负责|帮忙|帮她|帮小雨|陪她|陪小雨|搭|修|写了|写过|在写|开发|实现|调试)"
    r"(?:了|过|着)?\s*([^。；;，,\n]{2,48})"
)

SHARED_MARKERS = (
    "我们",
    "咱们",
    "一起",
    "共同",
    "暗号",
    "意象",
    "故事",
    "项目",
    "承诺",
    "约定",
    "关系",
    "记忆",
)

QUERY_HINTS = (
    ("likes", ("我喜欢", "我爱的", "我偏好", "喜欢的", "偏爱的")),
    ("dislikes", ("我不喜欢", "我讨厌", "我厌恶", "讨厌的", "不喜欢的")),
    ("boundary", ("我的雷点", "雷点", "边界")),
    ("participates_in", ("你参与", "你做", "你写", "你修", "你搭", "你帮", "你陪", "你负责")),
    ("shared_anchor", ("我们", "咱们", "我们的", "一起", "共同")),
)

NOISY_OBJECTS = {
    "你",
    "你啦",
    "你呀",
    "哥哥",
    "老公",
    "宝宝",
    "宝贝",
    "老婆",
    "亲爱的",
    "它",
    "这个",
    "这个东西",
    "这件事",
    "这类东西",
    "它的原因",
    "原因",
}


class EntityEdgeStore:
    """Small JSONL-backed index for person/object memory hints."""

    def __init__(self, config: dict):
        state_dir = config.get("state_dir") or os.path.join(
            os.path.dirname(os.path.abspath(config.get("buckets_dir", "buckets"))),
            "state",
        )
        self.path = os.path.join(state_dir, "entity_edges.jsonl")
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def add_edge(
        self,
        subject: str,
        relation: str,
        object_text: str,
        bucket_id: str,
        confidence: float = 0.65,
        evidence: str = "",
        created_at: str | None = None,
    ) -> dict | None:
        edge = self._normalize(
            {
                "subject": subject,
                "relation": relation,
                "object_text": object_text,
                "bucket_id": bucket_id,
                "confidence": confidence,
                "evidence": evidence,
                "created_at": created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
        )
        if not edge:
            return None
        edges = self.list_edges()
        replaced = False
        for index, existing in enumerate(edges):
            if self._same_edge(existing, edge):
                if float(existing.get("confidence", 0.0)) <= edge["confidence"]:
                    edges[index] = edge
                replaced = True
                break
        if not replaced:
            edges.append(edge)
        self._write_all(edges)
        return edge

    def add_edges(self, edges: list[dict[str, Any]]) -> list[dict]:
        saved = []
        for edge in edges or []:
            if not isinstance(edge, dict):
                continue
            saved_edge = self.add_edge(
                edge.get("subject"),
                edge.get("relation"),
                edge.get("object_text") or edge.get("object"),
                edge.get("bucket_id"),
                edge.get("confidence", 0.65),
                edge.get("evidence", ""),
                edge.get("created_at"),
            )
            if saved_edge:
                saved.append(saved_edge)
        return saved

    def replace_bucket_edges(self, bucket_id: str, edges: list[dict[str, Any]]) -> list[dict]:
        bucket_id = str(bucket_id or "").strip()
        if not bucket_id:
            return []
        kept = [edge for edge in self.list_edges() if edge.get("bucket_id") != bucket_id]
        for edge in edges or []:
            if isinstance(edge, dict):
                edge["bucket_id"] = bucket_id
                normalized = self._normalize(edge)
                if normalized:
                    kept.append(normalized)
        deduped = self._dedupe(kept)
        self._write_all(deduped)
        return [edge for edge in deduped if edge.get("bucket_id") == bucket_id]

    def list_edges(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        edges = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                edge = self._normalize(raw)
                if edge:
                    edges.append(edge)
        return edges

    def delete_for_bucket(self, bucket_id: str) -> int:
        bucket_id = str(bucket_id or "").strip()
        if not bucket_id:
            return 0
        edges = self.list_edges()
        kept = [edge for edge in edges if edge.get("bucket_id") != bucket_id]
        deleted = len(edges) - len(kept)
        if deleted:
            self._write_all(kept)
        return deleted

    def match_query(
        self,
        query: str,
        identity: dict | None,
        *,
        bucket_ids: set[str] | list[str] | None = None,
        min_score: float = 0.48,
    ) -> dict[str, dict[str, Any]]:
        hints = entity_query_hints(query, identity)
        if not hints:
            return {}
        allowed = {str(bucket_id) for bucket_id in bucket_ids or [] if str(bucket_id or "").strip()}
        limited = bool(bucket_ids is not None)
        matches: dict[str, dict[str, Any]] = {}
        for edge in self.list_edges():
            bucket_id = str(edge.get("bucket_id") or "")
            if not bucket_id or (limited and bucket_id not in allowed):
                continue
            score = score_entity_edge_for_query(edge, hints)
            if score < min_score:
                continue
            current = matches.get(bucket_id)
            if current is None or score > float(current.get("score", 0.0)):
                matches[bucket_id] = {
                    **edge,
                    "score": round(score, 4),
                }
        return matches

    def _write_all(self, edges: list[dict]) -> None:
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8", newline="\n") as f:
            for edge in self._dedupe(edges):
                f.write(json.dumps(edge, ensure_ascii=False, sort_keys=True) + "\n")
        os.replace(tmp_path, self.path)

    def _normalize(self, edge: dict) -> dict | None:
        subject = str(edge.get("subject") or "").strip()
        relation = str(edge.get("relation") or edge.get("predicate") or "").strip()
        object_text = _clean_entity_object(edge.get("object_text") or edge.get("object") or "")
        bucket_id = str(edge.get("bucket_id") or "").strip()
        if not subject or not relation or not object_text or not bucket_id:
            return None
        if relation not in ENTITY_RELATIONS:
            return None
        return {
            "subject": subject[:80],
            "relation": relation,
            "object_text": object_text[:80],
            "object_key": _compact_key(object_text),
            "bucket_id": bucket_id,
            "confidence": _clamp(edge.get("confidence", 0.65)),
            "evidence": _clip_text(edge.get("evidence") or "", 180),
            "created_at": str(edge.get("created_at") or ""),
        }

    @staticmethod
    def _same_edge(left: dict, right: dict) -> bool:
        return (
            left.get("subject") == right.get("subject")
            and left.get("relation") == right.get("relation")
            and left.get("object_key") == right.get("object_key")
            and left.get("bucket_id") == right.get("bucket_id")
        )

    def _dedupe(self, edges: list[dict]) -> list[dict]:
        by_key: dict[tuple[str, str, str, str], dict] = {}
        for raw in edges or []:
            edge = self._normalize(raw)
            if not edge:
                continue
            key = (
                edge["subject"],
                edge["relation"],
                edge["object_key"],
                edge["bucket_id"],
            )
            existing = by_key.get(key)
            if existing is None or edge["confidence"] > existing["confidence"]:
                by_key[key] = edge
        return list(by_key.values())


def extract_entity_edges_from_bucket(bucket: dict, identity: dict | None = None) -> list[dict]:
    if not isinstance(bucket, dict):
        return []
    bucket_id = str(bucket.get("id") or "").strip()
    if not bucket_id:
        return []
    identity = identity or identity_names(None)
    meta = bucket.get("metadata") if isinstance(bucket.get("metadata"), dict) else {}
    title = str(meta.get("name") or bucket.get("name") or "").strip()
    text = _bucket_entity_text(bucket)
    relation_text = _bucket_relation_text(bucket)
    if not text:
        return []

    edges: list[dict] = []
    user_subject = _canonical_user_subject(identity)
    ai_subject = _canonical_ai_subject(identity)
    user_pattern = _terms_pattern(_user_terms(identity))
    ai_pattern = _terms_pattern(_ai_terms(identity))

    for relation, tail in USER_RELATION_SPECS:
        pattern = re.compile(user_pattern + tail, re.IGNORECASE)
        for match in pattern.finditer(relation_text):
            obj = _clean_entity_object(match.group(1))
            if not _valid_entity_object(obj, identity):
                continue
            edges.append(
                _edge(
                    user_subject,
                    relation,
                    obj,
                    bucket_id,
                    confidence=0.82 if relation in {"likes", "dislikes", "prefers"} else 0.72,
                    evidence=_clip_text(match.group(0), 160),
                )
            )
        continuation_pattern = re.compile(tail, re.IGNORECASE)
        for match in continuation_pattern.finditer(relation_text):
            if not _has_user_context_before(relation_text, match.start(), identity):
                continue
            obj = _clean_entity_object(match.group(1))
            if not _valid_entity_object(obj, identity):
                continue
            edges.append(
                _edge(
                    user_subject,
                    relation,
                    obj,
                    bucket_id,
                    confidence=0.74 if relation in {"likes", "dislikes", "prefers"} else 0.66,
                    evidence=_clip_text(match.group(0), 160),
                )
            )

    for match in re.compile(ai_pattern + AI_PARTICIPATION_TAIL, re.IGNORECASE).finditer(relation_text):
        obj = _clean_entity_object(match.group(1))
        if not _valid_entity_object(obj, identity):
            continue
        edges.append(
            _edge(
                ai_subject,
                "participates_in",
                obj,
                bucket_id,
                confidence=0.68,
                evidence=_clip_text(match.group(0), 160),
            )
        )

    if _looks_shared_anchor(text, title, identity):
        shared_object = _shared_anchor_object(title, text)
        if shared_object:
            edges.append(
                _edge(
                    _shared_subject(identity),
                    "shared_anchor",
                    shared_object,
                    bucket_id,
                    confidence=0.66,
                    evidence=_clip_text(title or text, 160),
                )
            )

    return _dedupe_edges(edges)


def entity_query_hints(query: str, identity: dict | None = None) -> list[dict[str, Any]]:
    identity = identity or identity_names(None)
    text = strip_wikilinks(str(query or "")).strip()
    compact = _compact_key(text)
    if not compact:
        return []
    hints: list[dict[str, Any]] = []
    for relation, markers in QUERY_HINTS:
        if not any(_compact_key(marker) in compact for marker in markers):
            continue
        if relation == "participates_in":
            subject = _canonical_ai_subject(identity)
            relations = {"participates_in"}
        elif relation == "shared_anchor":
            subject = _shared_subject(identity)
            relations = {"shared_anchor"}
        elif relation == "boundary":
            subject = _canonical_user_subject(identity)
            relations = {"boundary", "dislikes"}
        else:
            subject = _canonical_user_subject(identity)
            relations = {relation}
            if relation == "likes":
                relations.add("prefers")
        hints.append(
            {
                "subject": subject,
                "relations": relations,
                "object_terms": _query_object_terms(text, relation),
            }
        )
    return hints


def score_entity_edge_for_query(edge: dict, hints: list[dict[str, Any]]) -> float:
    best = 0.0
    edge_subject = str(edge.get("subject") or "")
    edge_relation = str(edge.get("relation") or "")
    edge_object = _compact_key(edge.get("object_text") or "")
    edge_evidence = _compact_key(edge.get("evidence") or "")
    confidence = _clamp(edge.get("confidence", 0.65))
    for hint in hints or []:
        if edge_subject != hint.get("subject"):
            continue
        if edge_relation not in set(hint.get("relations") or []):
            continue
        score = 0.46 + confidence * 0.28
        object_terms = [_compact_key(term) for term in hint.get("object_terms") or [] if _compact_key(term)]
        if object_terms:
            if any(term in edge_object or term in edge_evidence for term in object_terms):
                score += 0.24
            else:
                score -= 0.18
        best = max(best, score)
    return max(0.0, min(1.0, best))


def _edge(
    subject: str,
    relation: str,
    object_text: str,
    bucket_id: str,
    *,
    confidence: float,
    evidence: str,
) -> dict:
    return {
        "subject": subject,
        "relation": relation,
        "object_text": object_text,
        "bucket_id": bucket_id,
        "confidence": confidence,
        "evidence": evidence,
    }


def _bucket_entity_text(bucket: dict) -> str:
    meta = bucket.get("metadata") if isinstance(bucket.get("metadata"), dict) else {}
    parts = [
        meta.get("name") or bucket.get("name") or "",
        " ".join(str(tag) for tag in meta.get("tags", []) or []),
        " ".join(str(domain) for domain in meta.get("domain", []) or []),
        bucket.get("content") or "",
    ]
    return strip_wikilinks("\n".join(str(part) for part in parts if part)).strip()


def _bucket_relation_text(bucket: dict) -> str:
    return strip_wikilinks(str(bucket.get("content") or "")).strip()


def _looks_shared_anchor(text: str, title: str, identity: dict) -> bool:
    compact_text = _compact_key(text)
    compact_title = _compact_key(title)
    has_user = any(_compact_key(term) in compact_text for term in _user_terms(identity))
    has_ai = any(_compact_key(term) in compact_text for term in _ai_terms(identity))
    has_we = any(marker in compact_text or marker in compact_title for marker in ("我们", "咱们", "一起", "共同"))
    has_marker = any(_compact_key(marker) in compact_text or _compact_key(marker) in compact_title for marker in SHARED_MARKERS)
    return has_marker and ((has_user and has_ai) or has_we)


def _has_user_context_before(text: str, start: int, identity: dict) -> bool:
    prefix = text[: max(0, start)]
    sentence = re.split(r"[。！？!?；;\n]", prefix)[-1]
    if not sentence:
        return False
    compact_sentence = _compact_key(sentence)
    if not compact_sentence:
        return False
    user_positions = [
        compact_sentence.rfind(_compact_key(term))
        for term in _user_terms(identity)
        if _compact_key(term) and _compact_key(term) in compact_sentence
    ]
    if not user_positions:
        return False
    ai_positions = [
        compact_sentence.rfind(_compact_key(term))
        for term in _ai_terms(identity)
        if _compact_key(term) and _compact_key(term) in compact_sentence
    ]
    return max(user_positions) >= max(ai_positions or [-1])


def _shared_anchor_object(title: str, text: str) -> str:
    title = _clean_entity_object(title)
    if title and _valid_object_key(title):
        return title[:80]
    first = re.split(r"[。！？!?；;\n]", text.strip(), maxsplit=1)[0]
    return _clean_entity_object(first)[:80]


def _query_object_terms(query: str, relation: str) -> list[str]:
    text = strip_wikilinks(str(query or ""))
    for marker in (
        "我喜欢的",
        "我喜欢",
        "我爱的",
        "我偏好",
        "偏爱的",
        "我不喜欢的",
        "我不喜欢",
        "我讨厌的",
        "我讨厌",
        "我的雷点",
        "你参与的",
        "你参与",
        "你做的",
        "你做",
        "你写的",
        "你写",
        "你修的",
        "你修",
        "你搭的",
        "你搭",
        "我们的",
        "我们",
        "咱们",
        "一起",
        "共同",
    ):
        text = text.replace(marker, " ")
    text = re.sub(r"(什么|哪些|哪个|哪段|哪条|记忆|事情|东西|相关|关于|之前|以前|还记得|记得|吗|呢|呀|啊)", " ", text)
    terms = []
    for term in re.split(r"[\s，。！？、,.!?:：;；~～]+", text):
        clean = _clean_entity_object(term)
        if clean and len(_compact_key(clean)) >= 2:
            terms.append(clean)
    return terms[:4]


def _canonical_user_subject(identity: dict) -> str:
    return str(identity.get("user_display_name") or identity.get("user_name") or "用户").strip() or "用户"


def _canonical_ai_subject(identity: dict) -> str:
    return str(identity.get("ai_name") or "AI").strip() or "AI"


def _shared_subject(identity: dict) -> str:
    return f"{_canonical_user_subject(identity)}+{_canonical_ai_subject(identity)}"


def _user_terms(identity: dict) -> list[str]:
    return _unique_terms(
        [
            identity.get("user_display_name"),
            identity.get("user_name"),
            *(identity.get("user_aliases") or []),
            "用户",
            "她",
        ]
    )


def _ai_terms(identity: dict) -> list[str]:
    ai_name = _canonical_ai_subject(identity)
    return _unique_terms([ai_name, f"小{ai_name}"])


def _unique_terms(values: list[Any]) -> list[str]:
    output = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in output:
            output.append(text)
    return output


def _terms_pattern(terms: list[str]) -> str:
    escaped = [re.escape(term) for term in sorted(terms, key=len, reverse=True) if term]
    return r"(?:" + "|".join(escaped or [r"a^"]) + r")"


def _clean_entity_object(value: Any) -> str:
    text = strip_wikilinks(str(value or "")).strip()
    text = re.sub(r"^[“\"'「『（(]+|[”\"'」』）)]+$", "", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"(这件事|这个设定|这类东西|的时候)$", "", text)
    return text[:80].strip("。；;，,、 :：")


def _valid_entity_object(obj: str, identity: dict) -> bool:
    if not _valid_object_key(obj):
        return False
    noisy = set(NOISY_OBJECTS)
    ai_name = _canonical_ai_subject(identity)
    noisy.update({ai_name, f"小{ai_name}"})
    return _compact_key(obj) not in {_compact_key(item) for item in noisy}


def _valid_object_key(obj: str) -> bool:
    key = _compact_key(obj)
    return bool(key and len(key) >= 2)


def _dedupe_edges(edges: list[dict]) -> list[dict]:
    deduped: dict[tuple[str, str, str, str], dict] = {}
    for edge in edges:
        key = (
            str(edge.get("subject") or ""),
            str(edge.get("relation") or ""),
            _compact_key(edge.get("object_text") or ""),
            str(edge.get("bucket_id") or ""),
        )
        existing = deduped.get(key)
        if existing is None or float(edge.get("confidence", 0.0)) > float(existing.get("confidence", 0.0)):
            deduped[key] = edge
    return list(deduped.values())


def _compact_key(value: Any) -> str:
    return re.sub(r"[\s。；;，,、：:\"'“”‘’「」『』【】\[\]（）()!?！？~～._-]+", "", str(value or "").lower())


def _clip_text(value: Any, limit: int) -> str:
    text = " ".join(strip_wikilinks(str(value or "")).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _clamp(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.65
    return max(0.0, min(1.0, round(number, 3)))
