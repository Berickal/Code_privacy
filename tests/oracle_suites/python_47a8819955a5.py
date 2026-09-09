"""Oracle suite for python_47a8819955a5  —  NEEDS_REVIEW
Function: fill_first_input
Spec (docstring):
    使用 Camoufox 完成 Exa 注册
    思路：通过邮箱验证码登录，跳过 onboarding，并提取默认 API Key

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import fill_first_input  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert fill_first_input(...) == ...
    assert callable(fill_first_input)
