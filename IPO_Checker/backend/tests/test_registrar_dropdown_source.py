"""Tests for the registrar dropdown discovery source.

The browser-touching parts of ``registrar_dropdown_source`` are integration
territory, but the decision that matters most — whether an empty dropdown means
"no live IPOs" or "the DOM changed" — is a pure function and is covered here.
"""

from ipo_sync.sources.registrar_dropdown_source import _empty_read_outcome


def test_server_rendered_empty_select_is_conclusive():
    """A server-rendered select with only its placeholder is a trustworthy
    "nothing checkable right now" read, so absence can be acted on."""
    outcome, reason = _empty_read_outcome({"empty_is_conclusive": True})

    assert outcome == "conclusive"
    assert reason is None


def test_ajax_empty_select_is_treated_as_unread():
    """For a normal (AJAX-loaded) select, an empty list is far more likely a
    half-loaded DOM than a genuinely empty portal, so it must not be acted on."""
    outcome, reason = _empty_read_outcome({"empty_is_conclusive": False})

    assert outcome == "failed"
    assert reason == "no options returned (possible DOM change)"


def test_adapter_without_the_flag_defaults_to_unread():
    """The flag is opt-in: only a registrar we have verified is server-rendered
    gets the conclusive-empty interpretation."""
    outcome, _ = _empty_read_outcome({})

    assert outcome == "failed"
