# SPDX-License-Identifier: MIT
"""Thin REIT case entry; the workbench does not duplicate professional calculations."""
from specialist_loader import call,LAST_PROVENANCE
from review_io import cli

def review(spec):
    result=call('reits','public_case','review',spec)
    return dict(result,engineProvenance=LAST_PROVENANCE['reits'])

if __name__=='__main__':raise SystemExit(cli({'review':review},'真实REIT资料研究'))
