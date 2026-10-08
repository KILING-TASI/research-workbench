import unittest
from collection_quality_brief import brief
class ReportAcquisitionStatus(unittest.TestCase):
 def row(self):
  return {'code':'159869','kind':'etf','history':[{'date':'2026-09-30','close':1}], 'financials':[], 'announcements':[], 'components':{'history':{'status':'cached-after-failure','error':'TimeoutError','count':1},'financials':{'status':'unsupported','reason':'未接入','count':0},'announcements':{'status':'failed','error':'返回空','count':0}}}
 def test_partial_is_explained_per_component(self):
  t=brief({'asOf':'2026-09-30','rows':[self.row()]})
  self.assertIn('| 历史行情 | 刷新失败，保留旧资料 | 1 |',t)
  self.assertIn('| 财务摘要 | 此链路尚未支持 | 0 |',t)
  self.assertIn('| 公告元数据 | 未取得 | 0 |',t)
  self.assertIn('证券名称',t);self.assertIn('不表示原文核验',t)
 def test_returned_name_is_not_original_verification(self):
  r=self.row();r['identity']={'code':'159869','name':'样本ETF'}
  t=brief({'asOf':'2026-09-30','rows':[r]})
  self.assertIn('名称：样本ETF',t);self.assertIn('不等于基金合同',t)
 def test_success_and_cache_are_distinct(self):
  r=self.row();r['components']['history']={'status':'success','count':1}
  fresh=brief({'rows':[r]});r['components']['history']['status']='cached'
  saved=brief({'rows':[r]})
  self.assertIn('| 历史行情 | 本次取得 | 1 |',fresh)
  self.assertIn('| 历史行情 | 读取已保存资料 | 1 |',saved)
