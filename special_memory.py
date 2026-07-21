"""Isolated durable stores for plans, letters, and AI self-knowledge."""

from __future__ import annotations

import asyncio
import base64
import json
import math
import re
from datetime import date as date_type
from typing import Any

from utils import now_iso


SPECIAL_MEMORY_TYPES = frozenset({"plan", "letter", "i"})
PLAN_STATUSES = frozenset({"active", "resolved", "abandoned"})
I_ASPECTS = frozenset(
    {"nature", "values", "patterns", "limits", "becoming", "uncertainty", "stance"}
)


def is_special_memory_metadata(metadata: dict | None) -> bool:
    return str((metadata or {}).get("type") or "").lower() in SPECIAL_MEMORY_TYPES


def append_plan_change_log(
    metadata: dict,
    *,
    field: str,
    old_value: Any,
    new_value: Any,
    reason: str = "",
) -> list[dict]:
    history = metadata.get("change_log")
    if not isinstance(history, list):
        history = []
    entry = {
        "at": now_iso(),
        "field": str(field),
        "from": old_value,
        "to": new_value,
    }
    if reason:
        entry["reason"] = str(reason)
    return [*history, entry]


class SpecialMemoryService:
    """CRUD and lifecycle behavior that must bypass ordinary memory mutation."""

    def __init__(self, config: dict, bucket_mgr, embedding_engine=None, dehydrator=None, logger=None):
        self.config = config
        self.bucket_mgr = bucket_mgr
        self.embedding_engine = embedding_engine
        self.dehydrator = dehydrator
        self.logger = logger
        self._write_lock = asyncio.Lock()

    @staticmethod
    def _required_text(value: Any, field: str, *, preserve: bool = False) -> str:
        text = str(value if value is not None else "")
        if not text.strip():
            raise ValueError(f"{field} must not be empty")
        if len(text.encode("utf-8")) > 50 * 1024:
            raise ValueError(f"{field} exceeds 50 KiB")
        return text if preserve else text.strip()

    @staticmethod
    def _weight(value: Any) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.5
        if not math.isfinite(number):
            number = 0.5
        return max(0.0, min(1.0, number))

    async def _index(self, bucket_id: str, content: str) -> None:
        engine = self.embedding_engine
        if engine is None or not getattr(engine, "enabled", False):
            return
        try:
            await engine.generate_and_store(bucket_id, content)
        except Exception as exc:
            if self.logger:
                self.logger.warning("Special-memory embedding failed for %s: %s", bucket_id, exc)

    async def plan(
        self,
        content: str,
        *,
        status: str = "active",
        related_bucket: str = "",
        weight: float = 0.5,
        why_remembered: str = "",
    ) -> dict:
        body = self._required_text(content, "content")
        normalized_status = str(status or "active").strip().lower()
        if normalized_status not in PLAN_STATUSES:
            raise ValueError("status must be active, resolved, or abandoned")
        related_bucket = str(related_bucket or "").strip()
        if related_bucket and not await self.bucket_mgr.get(related_bucket):
            raise ValueError(f"related_bucket not found: {related_bucket}")

        async with self._write_lock:
            for bucket in await self.bucket_mgr.list_all(include_archive=True):
                meta = bucket.get("metadata", {})
                if (
                    meta.get("type") == "plan"
                    and meta.get("status", "active") == "active"
                    and bucket.get("content", "") == body
                ):
                    return {"bucket_id": bucket["id"], "deduplicated": True, "status": "active"}

            created_at = now_iso()
            change_log = [{
                "at": created_at,
                "field": "status",
                "from": None,
                "to": normalized_status,
                "reason": "created",
            }]
            bucket_id = await self.bucket_mgr.create(
                content=body,
                tags=["__plan__"],
                importance=7,
                domain=["plan"],
                bucket_type="plan",
                name=body[:48],
                source="plan",
                extra_metadata={
                    "status": normalized_status,
                    "weight": self._weight(weight),
                    "why_remembered": str(why_remembered or "").strip(),
                    "related_bucket": related_bucket,
                    "change_log": change_log,
                    "dont_surface": True,
                },
            )
        await self._index(bucket_id, body)
        return {"bucket_id": bucket_id, "deduplicated": False, "status": normalized_status}

    async def letter_write(
        self,
        content: str,
        *,
        author: str,
        date: str = "",
        title: str = "",
        user_name: str = "",
        ai_name: str = "",
    ) -> dict:
        body = self._required_text(content, "content", preserve=True)
        author_text = self._required_text(author, "author")
        ai_label = str(ai_name or "").strip() or "AI"
        if author_text.casefold() in {"ai", "claude", ai_label.casefold()}:
            author_text = ai_label
        elif author_text.casefold() == "user":
            author_text = "user"
        date_text = str(date or "").strip() or date_type.today().isoformat()
        async with self._write_lock:
            bucket_id = await self.bucket_mgr.create(
                content=body,
                tags=["__letter__"],
                importance=10,
                domain=["letter"],
                bucket_type="letter",
                name=str(title or "").strip() or f"Letter from {author_text}",
                source="letter_write",
                date=date_text,
                extra_metadata={
                    "author": author_text,
                    "title": str(title or "").strip(),
                    "letter_date": date_text,
                    "user_name": str(user_name or "").strip(),
                    "ai_name": str(ai_name or "").strip(),
                    "dont_surface": True,
                    "verbatim_content_b64": base64.b64encode(body.encode("utf-8")).decode("ascii"),
                },
            )
        await self._index(bucket_id, body)
        return {"bucket_id": bucket_id, "author": author_text, "date": date_text}

    async def letter_read(
        self,
        *,
        query: str = "",
        author: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 10,
    ) -> list[dict]:
        limit = max(1, min(50, int(limit or 10)))
        letters = []
        for bucket in await self.bucket_mgr.list_all(include_archive=True):
            meta = bucket.get("metadata", {})
            if meta.get("type") != "letter":
                continue
            if author and str(meta.get("author", "")).casefold() != author.strip().casefold():
                continue
            letter_date = str(meta.get("letter_date") or meta.get("date") or meta.get("created", ""))
            if date_from and letter_date < date_from.strip():
                continue
            if date_to and letter_date > date_to.strip():
                continue
            letters.append(bucket)

        scores: dict[str, float] = {}
        query_text = str(query or "").strip()
        if query_text and self.embedding_engine is not None and getattr(self.embedding_engine, "enabled", False):
            try:
                scores = dict(await self.embedding_engine.search_similar(query_text, top_k=max(50, limit * 5)))
            except Exception:
                scores = {}
        if query_text:
            terms = [term.casefold() for term in re.findall(r"[\w\u4e00-\u9fff]+", query_text)]
            for bucket in letters:
                haystack = " ".join([
                    bucket.get("content", ""),
                    str(bucket.get("metadata", {}).get("title", "")),
                    str(bucket.get("metadata", {}).get("author", "")),
                ]).casefold()
                lexical = sum(1.0 for term in terms if term in haystack)
                scores[bucket["id"]] = max(scores.get(bucket["id"], 0.0), lexical)
            letters = [item for item in letters if scores.get(item["id"], 0.0) > 0]

        letters.sort(
            key=lambda item: (
                scores.get(item["id"], 0.0),
                str(item.get("metadata", {}).get("letter_date") or item.get("metadata", {}).get("date", "")),
                str(item.get("metadata", {}).get("created", "")),
            ),
            reverse=True,
        )
        return letters[:limit]

    async def I(self, content: str = "", *, aspect: str = "", read: bool = False, limit: int = 20) -> dict | list[dict]:
        body = str(content if content is not None else "")
        limit = max(1, min(100, int(limit or 20)))
        if read or not body.strip():
            entries = [
                item for item in await self.bucket_mgr.list_all(include_archive=True)
                if item.get("metadata", {}).get("type") == "i"
            ]
            if aspect:
                entries = [item for item in entries if item.get("metadata", {}).get("aspect") == aspect]
            return sorted(entries, key=lambda item: item.get("metadata", {}).get("created", ""), reverse=True)[:limit]

        normalized_aspect = str(aspect or "").strip().lower()
        if normalized_aspect and normalized_aspect not in I_ASPECTS:
            raise ValueError("aspect must be one of: " + ", ".join(sorted(I_ASPECTS)))
        body = self._required_text(body, "content", preserve=True)
        async with self._write_lock:
            bucket_id = await self.bucket_mgr.create(
                content=body,
                tags=["__i__", "self-anchor"] + ([f"aspect:{normalized_aspect}"] if normalized_aspect else []),
                importance=6,
                domain=["self"],
                bucket_type="i",
                name=f"I: {normalized_aspect}",
                source="I",
                extra_metadata={
                    "aspect": normalized_aspect,
                    "self_anchor": True,
                    "dont_surface": True,
                },
            )
        await self._index(bucket_id, body)
        return {"bucket_id": bucket_id, "aspect": normalized_aspect}

    async def update_plan(self, bucket_id: str, *, status=None, weight=None, why_remembered=None, reason="trace") -> dict:
        bucket = await self.bucket_mgr.get(bucket_id)
        if not bucket or bucket.get("metadata", {}).get("type") != "plan":
            raise ValueError(f"not a plan bucket: {bucket_id}")
        meta = bucket["metadata"]
        extra: dict[str, Any] = {}
        history = meta.get("change_log") if isinstance(meta.get("change_log"), list) else []
        if status is not None:
            normalized = str(status).strip().lower()
            if normalized not in PLAN_STATUSES:
                raise ValueError("status must be active, resolved, or abandoned")
            if normalized != meta.get("status", "active"):
                history = append_plan_change_log(meta | {"change_log": history}, field="status", old_value=meta.get("status", "active"), new_value=normalized, reason=reason)
                extra["status"] = normalized
                extra["resolved"] = normalized == "resolved"
        if weight is not None:
            normalized_weight = self._weight(weight)
            if normalized_weight != self._weight(meta.get("weight", 0.5)):
                history = append_plan_change_log(meta | {"change_log": history}, field="weight", old_value=meta.get("weight", 0.5), new_value=normalized_weight, reason=reason)
                extra["weight"] = normalized_weight
        if why_remembered is not None:
            text = str(why_remembered)
            if text != str(meta.get("why_remembered", "")):
                history = append_plan_change_log(meta | {"change_log": history}, field="why_remembered", old_value=meta.get("why_remembered", ""), new_value=text, reason=reason)
                extra["why_remembered"] = text
        if history != meta.get("change_log"):
            extra["change_log"] = history
        if not extra:
            return bucket
        resolved_flag = extra.pop("resolved", None)
        kwargs = {"extra_metadata": extra}
        if resolved_flag is not None:
            kwargs["resolved"] = resolved_flag
        await self.bucket_mgr.update(bucket_id, **kwargs)
        related = str(meta.get("related_bucket") or "")
        if extra.get("status") == "resolved" and related:
            await self.bucket_mgr.update(related, resolved=True)
        return await self.bucket_mgr.get(bucket_id)

    async def check_plan_resolution(self, event_bucket_id: str, event_content: str) -> list[str]:
        cfg = self.config.get("plan", {}).get("auto_resolution", {})
        if not cfg.get("enabled", False):
            return []
        if self.embedding_engine is None or not getattr(self.embedding_engine, "enabled", False):
            return []
        client = getattr(self.dehydrator, "client", None)
        model = getattr(self.dehydrator, "model", "")
        if client is None:
            return []
        threshold = float(cfg.get("vector_threshold", 0.7))
        confidence_threshold = float(cfg.get("confidence_threshold", 0.7))
        top_k = max(1, min(50, int(cfg.get("top_k", 8))))
        active_plans = {
            item["id"]: item
            for item in await self.bucket_mgr.list_all(include_archive=False)
            if item.get("metadata", {}).get("type") == "plan"
            and item.get("metadata", {}).get("status", "active") == "active"
        }
        candidates = [
            (bucket_id, score) for bucket_id, score in await self.embedding_engine.search_similar(event_content, top_k=top_k * 4)
            if bucket_id in active_plans and score >= threshold
        ][:top_k]
        resolved_ids: list[str] = []
        for plan_id, similarity in candidates:
            prompt = (
                "Judge conservatively whether this new event is explicit evidence that the plan is fully completed. "
                "Intent, progress, discussion, or ambiguity are not completion. Return JSON only: "
                '{"resolved":false,"confidence":0.0,"reason":""}.\n\n'
                f"PLAN:\n{active_plans[plan_id].get('content', '')}\n\nEVENT:\n{event_content}"
            )
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                raw = response.choices[0].message.content or "{}"
                match = re.search(r"\{.*\}", raw, re.S)
                verdict = json.loads(match.group(0) if match else "{}")
                confidence = float(verdict.get("confidence", 0))
                if verdict.get("resolved") is True and confidence >= confidence_threshold:
                    reason = f"auto-resolution from {event_bucket_id}; similarity={similarity:.3f}; {verdict.get('reason', '')}"
                    await self.update_plan(plan_id, status="resolved", reason=reason)
                    await self.bucket_mgr.update(plan_id, extra_metadata={"resolved_by": event_bucket_id, "resolution_reason": verdict.get("reason", "")})
                    resolved_ids.append(plan_id)
            except Exception as exc:
                if self.logger:
                    self.logger.warning("Plan resolution check failed for %s: %s", plan_id, exc)
        return resolved_ids
