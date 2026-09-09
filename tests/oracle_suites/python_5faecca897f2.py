"""Oracle suite for python_5faecca897f2  —  NEEDS_REVIEW
Function: transcribe_audio
Spec (docstring):
    Qwen3 ASR demo for OpenArc's OpenAI-compatible transcription endpoint.

    Uses the OpenAI Python library. Assumes the server is already running.

    Usage:
        OPENARC_API_KEY=sk-... python demos/qwen3_asr_transcribe.py /path/to/audio.wav --model qwen3_asr

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import transcribe_audio  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert transcribe_audio(...) == ...
    assert callable(transcribe_audio)
