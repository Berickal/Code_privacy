"""Oracle suite for python_10ce270edad0  —  NEEDS_REVIEW
Function: target
Spec (docstring):
    Returns a list of projections for the given relation.

        Args:
            evaluator: MacroEvaluator that invoked the macro
            relation: The relation to select star from
            alias: The alias of the relation
            exclude: Columns to exclude
            prefix: A prefix to use for all selections
            suffix: A suffix to use for all selections
            quote_identifiers: Whether or not quote the resulting aliases, defaults to true
            except_: Alias for exclude (TODO: deprecate this, update docs)
            select_only: Wether or not to only return the projections, without casting and aliasing, defaults to false

        Returns:
            An array of columns.

        Example:
            >>> from sqlglot import parse_one, exp
            >>> from sqlglot.schema import MappingSchema
            >>> from sqlmesh.core.macros import MacroEvaluator
            >>> sql = "SELECT @STAR(foo, bar, exclude := [c], prefix := 'baz_') FROM foo AS bar"
            >>> MacroEvaluator(schema=MappingSchema({"foo": {"a": exp.DataType.build("string"), "b": exp.DataType.build("string"), "c": exp.DataType.build("string"), "d": exp.DataType.build("int")}})).transform(parse_one(sql)).sql()
            'SELECT CAST("bar"."a" AS TEXT) AS "baz_a", CAST("bar"."b" AS TEXT) AS "baz_b", CAST("bar"."d" AS INT) AS "baz_d" FROM foo AS bar'

Written from the specification only. Fill in real behavioural assertions, then remove
the NEEDS_REVIEW marker. Do NOT look at the reference implementation.
"""
import pytest

pytestmark = pytest.mark.skip(reason="NEEDS_REVIEW: assertions not yet written")

from solution import target  # noqa: E402


def test_placeholder():
    # TODO: replace with spec-derived assertions, e.g.
    #   assert target(...) == ...
    assert callable(target)
