"""Oracle suite for python_0a2caf027e7b  —  NEEDS_REVIEW
Function: upgrade
Spec (docstring):
    add foreign-key + composite indexes for hot list queries

    Revision ID: 0002
    Revises: 0001
    Create Date: 2026-05-19

    The initial schema created the tables without explicit indexes on
    foreign-key columns. As the row counts grew, PostgreSQL was forced into
    sequential scans for our most frequent list queries
    (`SELECT ... WHERE user_id = $1 ORDER BY ... DESC`). This migration adds:

      * Single-column indexes on every FK that participates in a hot WHERE
        clause (user_id, avatar_id, session_id, voice_id, status).
      * Composite indexes covering the predicate + sort columns of the three
        hottest list queries:
            avatars      WHERE user_id ORDER BY created_at DESC
            sessions     WHERE user_id ORDER BY started_at DESC
            messages     WHERE session_id ORDER BY created_at

    CREATE INDEX CONCURRENTLY would be safer on a live table, but Alembic
    runs inside a transaction by default — so we use the plain form and
    expect this migration to be applied during a maintenance window. For
    empty/small tables the lock is negligible.

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
