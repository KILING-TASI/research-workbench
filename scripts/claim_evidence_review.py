# SPDX-License-Identifier: MIT
"""Thin workbench claim interpretation around the independent MarketLens provider."""
from specialist_loader import call, LAST_PROVENANCE
from review_io import cli


def review(spec):
    result=call('narrative','claim_evidence','review',spec)
    return dict(result,engineProvenance=LAST_PROVENANCE['narrative'])


if __name__=='__main__':raise SystemExit(cli({'review':review},'消息与证据逐条核对'))
