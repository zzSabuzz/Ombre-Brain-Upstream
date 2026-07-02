SELF_ANCHOR_TAG = "自我"
SELF_ANCHOR_ALIASES = {"self_anchor", "self_identity", "self-identity", "first_person_anchor", "first-person-anchor"}


def _tag_key(value: object) -> str:
    return str(value or "").strip()


def _tag_match(value: object) -> bool:
    text = _tag_key(value)
    return text == SELF_ANCHOR_TAG or text.lower() in SELF_ANCHOR_ALIASES


def is_self_anchor_metadata(meta: dict | None) -> bool:
    if not isinstance(meta, dict):
        return False
    if bool(meta.get("self_anchor")):
        return True
    domains = meta.get("domain", [])
    if isinstance(domains, str):
        domains = [item.strip() for item in domains.split(",")]
    if not isinstance(domains, (list, tuple, set)):
        domains = [domains]
    return any(_tag_match(domain) for domain in domains)


def is_self_anchor_bucket(bucket: dict | None) -> bool:
    if not isinstance(bucket, dict):
        return False
    meta = bucket.get("metadata", {}) if isinstance(bucket.get("metadata"), dict) else {}
    return is_self_anchor_metadata(meta)
