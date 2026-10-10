# SPDX-License-Identifier: MIT
"""Workbench explanation and archive around the independently maintained ETF calculation."""
from specialist_loader import call,LAST_PROVENANCE
from review_io import cli

def run(spec,method):
    value=call('etf','review',method,spec)
    return dict(conclusion='按声明ETF观察池计算，结果范围与假设见下方；不是全市场择优或实际交易。',result=value,engineProvenance=LAST_PROVENANCE['etf'],methodVersion=value['methodVersion'],limitations=value['limitations'],humanRows=[['观察对象',len(spec['rows'])],['研究截止',spec['asOf']],['计算入口','独立ETF引擎；工作台只解释和归档']])

def review(spec):return run(spec,'calculate')
def backtest(spec):return run(spec,'backtest')

if __name__=='__main__':raise SystemExit(cli({'review':review,'backtest':backtest},'ETF轮动研究'))
