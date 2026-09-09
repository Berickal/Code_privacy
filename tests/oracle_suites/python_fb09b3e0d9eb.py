"""Oracle suite for python_fb09b3e0d9eb  —  NEEDS_REVIEW
Function: make_driver
Spec (docstring):
    Real-robot gripper drivers for OmniLink bridges.

    Self-contained (no Webots / OmniSim-internal imports). The gripper ids
    match the sim registry in `omnilink_arm_bridge/_gripper_configs.py`, so
    `--gripper <id>` selects the same physical gripper in sim and on real
    hardware.

        from grippers import make_driver, GRIPPER_SPECS
        g = make_driver("robotiq_2f85")     # DryTransport by default
        g.connect(); g.grasp(); g.state()

    To talk to real hardware, build the driver with a concrete transport:

        from grippers.robotiq import Robotiq2FDriver
        from my_modbus import PymodbusTransport
        g = Robotiq2FDriver(max_width=0.085, transport=PymodbusTransport(host=...))

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import make_driver  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert make_driver(...) == ...
    assert callable(make_driver)
