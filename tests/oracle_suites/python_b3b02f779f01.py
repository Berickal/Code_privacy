"""Oracle suite for python_b3b02f779f01  —  NEEDS_REVIEW
Function: upgrade
Spec (docstring):
    add ON DELETE CASCADE to all child foreign keys

    Revision ID: 0003
    Revises: 0002
    Create Date: 2026-06-11

    The initial schema created every foreign key with the default NO ACTION.
    That made two user-facing flows return HTTP 500:

      * DELETE /sessions/{id} — every chatted session has an auto-titled row in
        `conversations` referencing it; the ORM only cascaded `messages`, so the
        delete hit an FK violation on `conversations.session_id`.
      * DELETE /avatars/{id} — any avatar that had ever been used in a session
        hit an FK violation on `sessions.avatar_id`.

    The ORM relationships now declare delete-orphan cascades (which fixes the
    SQLite test path too); this migration aligns the database so direct SQL or
    out-of-band deletes behave identically.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import upgrade  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert upgrade(...) == ...
    assert callable(upgrade)
