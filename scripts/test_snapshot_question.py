import unittest
from decimal import Decimal
from snapshot_question import answer

class Tests(unittest.TestCase):
    def spec(self):return {'holdings':[{'code':str(i),'name':'项目'+str(i),'marketValue':str(v),'weightPct':str(v),'valuationDate':None} for i,v in enumerate([40,30,20,10])],'totalMarketValue':'100','currency':'CNY','sourceVerification':'user-declared-not-verified','shareClassClues':[]}
    def test_top_three_money_not_risk_and_missing_dates(self):
        data,text=answer(self.spec())
        self.assertEqual(data['topCodes'],['0','1','2']);self.assertEqual(Decimal(data['topWeightPct']),90)
        self.assertIn('不能说风险',data['conclusion']);self.assertIn('4项未提供估值日期',text)
    def test_less_than_three_does_not_invent_items(self):
        s=self.spec();s['holdings']=s['holdings'][:2];s['totalMarketValue']='70'
        data,text=answer(s);self.assertEqual(len(data['topCodes']),2);self.assertIn('全部2项',data['conclusion'])
    def test_share_class_hint_not_automatically_confirmed(self):
        s=self.spec();s['shareClassClues']=[{'nameStem':'某基金','weightPct':'70'}]
        data,text=answer(s);self.assertIn('需核对官方',text);self.assertIn('没有自动合并',text)

if __name__=='__main__':unittest.main()
