"""Oracle suite for python_3f7bb9625489  —  NEEDS_REVIEW
Function: _extensions_dir
Spec (docstring):
    Generic extension loader.

    Optional packages dropped into ``backend/extensions/`` (gitignored, excluded
    from release bundles) are imported at boot and get ``register(app, csrf)``
    called. With the directory absent — every normal install — this whole module
    is a no-op. ``LDS_EXTENSIONS=0`` disables loading; ``LDS_EXTENSIONS_DIR``
    overrides the directory (used by tests).

    Extensions are trusted local code — but they load AFTER the network guard
    installs, so an extension's ``before_request`` hook can never answer a
    request the access-token gate would have refused (before_request hooks run
    in registration order). ``test_the_network_guard_outranks_extension_hooks``
    pins that ordering.

    Docker builds copy the whole ``backend`` directory into the image, so a
    developer's local ``backend/extensions/`` would enter an image built that
    way too. This is accepted because images are built from clean checkouts in
    CI and are never pushed to a registry.

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _extensions_dir  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _extensions_dir(...) == ...
    assert callable(_extensions_dir)
