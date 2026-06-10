"""Multimodal: telegram._classify recognises voice/photo as their
own kinds (was: silently IGNORED). Actual transcription/description
flows through the STT/Vision adapters; this test just confirms
classification."""

from __future__ import annotations

from veles.channels.telegram import _Kind, _classify


def test_voice_message_classified_as_voice() -> None:
    msg = {
        "chat": {"id": 1, "type": "private"},
        "voice": {
            "file_id": "AwACAg...",
            "duration": 3,
            "mime_type": "audio/ogg",
            "file_size": 12000,
        },
    }
    assert _classify(msg) == _Kind.VOICE


def test_audio_attachment_classified_as_voice() -> None:
    """Telegram delivers `audio` for music files; same handler path."""
    msg = {
        "chat": {"id": 1, "type": "private"},
        "audio": {
            "file_id": "BAACAg...",
            "duration": 60,
            "mime_type": "audio/mp3",
        },
    }
    assert _classify(msg) == _Kind.VOICE


def test_photo_message_classified_as_photo() -> None:
    """Telegram delivers `photo` as a list of size variants."""
    msg = {
        "chat": {"id": 1, "type": "private"},
        "photo": [
            {"file_id": "AgACA...small", "width": 90, "height": 90},
            {"file_id": "AgACA...large", "width": 1280, "height": 1280},
        ],
    }
    assert _classify(msg) == _Kind.PHOTO


def test_empty_photo_list_falls_through() -> None:
    """A photo with an empty array (shouldn't happen but defensive)
    isn't picked up as PHOTO."""
    msg = {
        "chat": {"id": 1, "type": "private"},
        "photo": [],
        "text": "caption-only",
    }
    assert _classify(msg) == _Kind.TEXT


def test_text_alongside_voice_still_voice() -> None:
    """When a voice message comes with a text caption, voice wins —
    the channel transcribes and folds the caption into the prompt."""
    msg = {
        "chat": {"id": 1, "type": "private"},
        "voice": {"file_id": "x", "duration": 2, "mime_type": "audio/ogg"},
        "text": "some caption",
    }
    assert _classify(msg) == _Kind.VOICE


def test_document_still_beats_voice() -> None:
    """Document is highest priority — a doc with a voice annotation
    (unusual but possible) routes to the document handler."""
    msg = {
        "chat": {"id": 1, "type": "private"},
        "document": {"file_id": "x", "file_name": "report.md"},
        "voice": {"file_id": "y", "duration": 1, "mime_type": "audio/ogg"},
    }
    assert _classify(msg) == _Kind.DOCUMENT


def test_plain_text_still_text() -> None:
    msg = {"chat": {"id": 1, "type": "private"}, "text": "hello"}
    assert _classify(msg) == _Kind.TEXT


def test_sticker_still_ignored() -> None:
    """A sticker-only message has no voice/photo/text — still IGNORED."""
    msg = {
        "chat": {"id": 1, "type": "private"},
        "sticker": {"file_id": "s1"},
    }
    assert _classify(msg) == _Kind.IGNORED
