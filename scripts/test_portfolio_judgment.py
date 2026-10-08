import unittest
from portfolio_history_report import judgment,contribution_question

class Judgment(unittest.TestCase):
 def test_contribution_question_unavailable_and_no_negative_rank(self):
  document={'holdings':[{'code':'a','name':'资产A'}]}
  data,text=contribution_question({'historical':{'portfolioPath':{'status':'not-requested'}}},document,'drag')
  self.assertEqual(data['status'],'unavailable');self.assertIn('不能判断',text)
  result={'historical':{'intervalStart':'2025-01-01','intervalEnd':'2025-12-31','portfolioPath':{'status':'calculated-observed-path','basis':'声明买入持有','returnContributions':[{'code':'a','contributionPp':5}]}}}
  data,text=contribution_question(result,document,'drag');self.assertEqual(data['leaderCodes'],[]);self.assertIn('没有负贡献项目',text)
 def test_named_contributions_explain_gain_and_drag_without_personal_attribution(self):
  result={'historical':{'portfolioPath':{'status':'calculated-observed-path','totalReturnPct':5,'endDrawdownPct':-2,'returnContributions':[{'code':'a','contributionPp':10},{'code':'b','contributionPp':-5}]}}}
  document={'holdings':[{'code':'a','name':'增长资产'},{'code':'b','name':'拖累资产'}]}
  text=judgment(result,document)
  self.assertIn('正向拉动最多的是增长资产',text);self.assertIn('拖累最多的是拖累资产',text);self.assertIn('不是单品收益率',text);self.assertIn('仍未回到',text)
 def test_positive_return_does_not_hide_unrecovered_drawdown(self):
  result={'historical':{'portfolioPath':{'status':'calculated-observed-path','totalReturnPct':10,'endDrawdownPct':-5}}}
  self.assertIn('仍未回到',judgment(result))
  result['historical']['portfolioPath']['totalReturnPct']=-10
  self.assertIn('负收益',judgment(result));self.assertNotIn('获得了正收益',judgment(result))
 def test_missing_path_cannot_claim_diversification(self):
  self.assertIn('不能据单品表现',judgment({'historical':{'portfolioPath':{'status':'disconnected-observations'}}}))
