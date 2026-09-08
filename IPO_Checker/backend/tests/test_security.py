"""Unit tests for the HMAC token scheme, masking, and client-IP resolution.

These are pure and deterministic — no server, no database.
"""

import json
import time

from starlette.requests import Request

from api import security


def _make_token(exp_offset_seconds: int) -> str:
    """Build a signed token with an explicit expiry offset, for the expiry test."""
    payload = {"exp": time.time() + exp_offset_seconds, "nonce": "test-nonce"}
    body = security._b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    return f"{body}.{security._sign(body)}"


def test_valid_token_verifies():
    assert security.verify_access_token(security.create_access_token())


def test_tampered_signature_is_rejected():
    token = security.create_access_token()
    body, signature = token.split(".", 1)
    flipped = "A" if signature[0] != "A" else "B"
    assert not security.verify_access_token(f"{body}.{flipped}{signature[1:]}")


def test_expired_token_is_rejected():
    assert not security.verify_access_token(_make_token(-10))


def test_malformed_tokens_are_rejected():
    assert not security.verify_access_token("nope")
    assert not security.verify_access_token("a.b.c")
    assert not security.verify_access_token("")


def test_mask_identifier_hides_all_but_last_four():
    assert security.mask_identifier("ABCDE1234F") == "***234F"


def test_mask_identifier_short_values_are_fully_hidden():
    assert security.mask_identifier("1234") == "***"


def test_mask_identifier_handles_empty_and_none():
    assert security.mask_identifier("") == ""
    assert security.mask_identifier(None) is None


def _request(headers, client=("5.6.7.8", 1234)):
    return Request(
        {"type": "http", "headers": headers, "client": client}
    )


def test_client_ip_uses_forwarded_header_first():
    req = _request([(b"x-forwarded-for", b"1.2.3.4, 10.0.0.1")])
    assert security.client_ip(req) == "1.2.3.4"


def test_client_ip_falls_back_to_remote_addr():
    req = _request([])
    assert security.client_ip(req) == "5.6.7.8"
