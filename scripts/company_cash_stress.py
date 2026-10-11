# SPDX-License-Identifier: MIT
"""Thin specialist cash stress entry; no duplicate valuation algorithm."""
from specialist_loader import call, LAST_PROVENANCE
from review_io import cli


def review(spec):
    result = call('financial', 'cash_stress', 'calculate', spec)
    return dict(result, engineProvenance=LAST_PROVENANCE['financial'])


if __name__ == '__main__': raise SystemExit(cli({'review': review}, '现金需求压力测算'))
