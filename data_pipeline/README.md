# data_pipeline/

This build does **not** require AWS. Corpus construction runs through
`exposure_gap.oracle` (GitHub commit API + SWH REST + a Stack v2 metadata bloom filter)
and `exposure_gap.corpus`.

`athena_reference/` keeps the Software Heritage Athena DDL and the four metadata queries
from the report (§6.4) as a **reference implementation** of an alternative
`MembershipOracle` / `TimestampOracle` backend. If an AWS account becomes available,
implement `AthenaOracle(MembershipOracle, TimestampOracle)` against these and pass it to
`CorpusBuilder` — nothing downstream changes.
