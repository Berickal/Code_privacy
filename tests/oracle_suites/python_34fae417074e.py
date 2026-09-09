"""Oracle suite for python_34fae417074e  —  NEEDS_REVIEW
Function: _default_bridge
Spec (docstring):
    Replay a RoboTwin bimanual demonstration in RoboVerse (ALOHA-AgileX).

    .. warning::

       **EXPERIMENTAL — not an out-of-the-box path.** Unlike examples 8 and 9, this
       one cannot be run from a clean RoboVerse install. It requires, on the local
       machine:

       - a cloned RoboTwin repo and its ~3.74 GB asset pack (incl. the ALOHA-AgileX
         ``embodiments.zip`` whose URDF this script loads);
       - a separate ``robotwin`` conda env, plus a curobo build for the local GPU
         arch (e.g. sm_120), to *collect* a bridge pickle with
         ``tools/robotwin_integration/collect_bridge.py``;
       - the resulting bridge pickle passed via ``--bridge``.

       It is also **only a partial-fidelity** view: the manipulated object is drawn
       as a primitive-cube proxy (not RoboTwin's real mesh), and only joint *motion*
       has been confirmed to replay -- task *success* has not been verified in
       RoboVerse. Treat this as a data-bridge demo, not a benchmark result.

    RoboTwin is a dual-arm manipulation benchmark whose demos are *single-embodiment
    bimanual*: one articulation (the ALOHA-AgileX: two arx5 arms on an AgileX base)
    whose action spans both arms. RoboVerse's trajectory format expresses this as a
    single robot entry keyed by name -- the one-robot case of the same name-keyed
    ``*_v2`` layout the multi-agent loader uses (see ``8_multiagent_dataset.py`` for
    the two-independent-agents case).

    This example is the *RoboVerse-side* half of the RoboTwin data bridge:

    1.  Load the sim-agnostic trajectory pickle produced (in the ``robotwin`` conda
        env) by ``tools/robotwin_integration/collect_bridge.py`` -- a dense dual-arm
        joint vector per frame plus initial object poses.
    2.  Convert it into RoboVerse's name-keyed ``*_v2`` format, mapping RoboTwin's
        14-D ``[L_arm(6), L_grip, R_arm(6), R_grip]`` vector onto the embodiment's
        joints (gripper value in ``[0, 1]`` -> joint via the embodiment's scale).
    3.  Load it back through the canonical loader ``get_traj`` and replay it on
        SAPIEN3 to video.

    Replay is dof-position-target driven: RoboTwin itself runs on SAPIEN3, so the
    same backend family reproduces the recorded joint motion closely (unlike the
    cross-simulator ManiSkill case, which uses state replay).

    Run (in the ``roboverse`` env, after collecting a bridge pickle)::

        MUJOCO_GL=egl python examples/10_robotwin_aloha_replay.py \\
            --bridge ~/projects/robotwin/data/_rv_bridge/beat_block_hammer.pkl --sim sapien3

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import _default_bridge  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert _default_bridge(...) == ...
    assert callable(_default_bridge)
