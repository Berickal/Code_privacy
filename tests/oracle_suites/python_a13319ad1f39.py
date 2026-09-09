"""Oracle suite for python_a13319ad1f39  —  NEEDS_REVIEW
Function: normalize_block
Spec (docstring):
    大宗交易采集（东财 datacenter RPT_DATA_BLOCKTRADE，按日全市场，写 block_trade）。

    T 日盘后当晚披露 → run(T) 采 T（17:30 时点若尚未出全由周 verify 补齐）。
    同股同日多笔无自然主键 → 表上全字段唯一索引 block_trade_uk 幂等去重。
    历史多年可全量 backfill（逐日、幂等跳过已采日）。

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import normalize_block  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert normalize_block(...) == ...
    assert callable(normalize_block)
