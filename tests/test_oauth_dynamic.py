import hashlib
from base64 import urlsafe_b64encode

from server import ChatGptOAuthProvider


def provider(tmp_path):
    return ChatGptOAuthProvider(
        client_id="legacy-client",
        client_secret="legacy-secret",
        access_token="access-token",
        refresh_token="refresh-token",
        redirect_uris=["https://claude.ai/api/mcp/auth_callback"],
        dynamic_clients_file=str(tmp_path / "state" / ".oauth_clients.json"),
    )


def test_dynamic_registration_persists_and_accepts_loopback_port_change(tmp_path):
    oauth = provider(tmp_path)
    registered = oauth.register_dynamic_client(
        {
            "client_name": "Codex CLI",
            "redirect_uris": ["http://127.0.0.1:1455/callback"],
            "token_endpoint_auth_method": "none",
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
        }
    )

    reloaded = provider(tmp_path)
    assert reloaded.valid_client_id(registered["client_id"])
    assert reloaded.valid_redirect_uri(
        registered["client_id"],
        "http://127.0.0.1:49152/callback",
    )
    assert not reloaded.valid_redirect_uri(
        registered["client_id"],
        "http://127.0.0.1:49152/different",
    )


def test_dynamic_registration_rejects_non_loopback_http(tmp_path):
    oauth = provider(tmp_path)
    try:
        oauth.register_dynamic_client(
            {
                "redirect_uris": ["http://example.com/callback"],
                "token_endpoint_auth_method": "none",
            }
        )
    except ValueError as exc:
        assert str(exc) == "invalid_redirect_uris"
    else:
        raise AssertionError("non-loopback HTTP redirect was accepted")


def test_dynamic_authorization_code_requires_matching_pkce(tmp_path):
    oauth = provider(tmp_path)
    registered = oauth.register_dynamic_client(
        {
            "client_name": "Codex CLI",
            "redirect_uris": ["http://localhost:1455/callback"],
        }
    )
    verifier = "v" * 64
    challenge = urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    code = oauth.create_authorization_code(
        registered["client_id"],
        "http://localhost:1455/callback",
        challenge,
        "S256",
    )

    assert not oauth.consume_authorization_code(
        code,
        registered["client_id"],
        "http://localhost:1455/callback",
        "x" * 64,
    )
    code = oauth.create_authorization_code(
        registered["client_id"],
        "http://localhost:1455/callback",
        challenge,
        "S256",
    )
    assert oauth.consume_authorization_code(
        code,
        registered["client_id"],
        "http://localhost:58321/callback",
        verifier,
    )


def test_legacy_client_remains_compatible_without_pkce(tmp_path):
    oauth = provider(tmp_path)
    redirect_uri = "https://claude.ai/api/mcp/auth_callback"

    assert oauth.valid_client_secret("legacy-client", "legacy-secret")
    assert oauth.valid_redirect_uri("legacy-client", redirect_uri)
    code = oauth.create_authorization_code("legacy-client", redirect_uri)
    assert oauth.consume_authorization_code(
        code,
        "legacy-client",
        redirect_uri,
        None,
    )
