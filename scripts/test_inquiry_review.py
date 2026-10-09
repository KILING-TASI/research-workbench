import unittest,copy
from inquiry_review import review
class Tests(unittest.TestCase):
 def spec(self):
  documents=[{'id':key,'entity':'教学公司','publishedAt':date,'version':'original','source':'https://example.org/'+key+'.pdf','sha256':'a'*64} for key,date in [('q','2025-05-01'),('r','2025-05-10')]]
  ref=lambda key:{'documentId':key,'physicalPage':2,'quote':'教学引句'}
  return {'entity':'教学公司','asOf':'2025-06-01','documents':documents,'questions':[{'id':'1','text':'教学应收问题','evidence':ref('q')},{'id':'2','text':'教学存货问题','evidence':ref('q')}],'responses':[{'id':'r1','questionIds':['1'],'evidence':ref('r'),'openItems':['尚缺账龄依据']} ]}
 def test_partial_ledger_preserves_missing_and_open_items(self):
  result=review(self.spec());self.assertEqual(result['missingReplyQuestionIds'],['2']);self.assertEqual(result['questions'][0]['replies'][0]['declaredOpenItems'],['尚缺账龄依据']);self.assertIn('不代表回复充分',result['conclusion'])
 def test_invalid_entity_date_page_and_target_rejected(self):
  for change in ('entity','future','page','target','duplicate'):
   spec=self.spec()
   if change=='entity':spec['documents'][1]['entity']='其他主体'
   if change=='future':spec['documents'][1]['publishedAt']='2026-01-01'
   if change=='page':spec['responses'][0]['evidence']['physicalPage']=True
   if change=='target':spec['responses'][0]['questionIds']=['3']
   if change=='duplicate':spec['questions'].append(copy.deepcopy(spec['questions'][0]))
   with self.assertRaises(ValueError):review(spec)
 def test_financial_link_preserves_basis_and_event_is_not_causality(self):
  spec=self.spec();ref={'documentId':'r','physicalPage':3,'quote':'教学字段'}
  spec['financialLinks']=[{'questionId':'1','fieldId':'receivables','entity':'教学公司','metric':'应收账款','period':'2025-03-31','scope':'consolidated','basis':'period-end','unit':'万元','reason':'问题明确涉及此科目','evidence':ref}]
  spec['events']=[{'questionId':'1','eventDate':'2025-05-09','reason':'公司补充公告','evidence':ref}]
  result=review(spec);self.assertEqual(result['questions'][0]['financialLinks'][0]['basis'],'period-end');self.assertEqual(result['questions'][0]['events'][0]['associationStatus'],'declared-link-not-causal-proof')
  spec['financialLinks'][0]['entity']='其他主体'
  with self.assertRaises(ValueError):review(spec)
 def test_same_pdf_and_page_are_read_once_per_review(self):
  import tempfile,hashlib,types,sys
  from pathlib import Path
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   raw=b'local teaching PDF';path=Path(tmp)/'a.pdf';path.write_bytes(raw);spec=self.spec()
   for doc in spec['documents']:doc.update(pdfPath=str(path),sha256=hashlib.sha256(raw).hexdigest())
   counts={'readers':0,'pages':0}
   def text():counts['pages']+=1;return '教学引句'
   def reader(stream):counts['readers']+=1;return types.SimpleNamespace(pages=[types.SimpleNamespace(extract_text=text)]*2)
   with patch.dict(sys.modules,{'pypdf':types.SimpleNamespace(PdfReader=reader)}):result=review(spec)
   self.assertEqual(counts,{'readers':1,'pages':1})
   self.assertTrue(all(q['questionEvidence']['pageVerification']=='quote-found-on-page' for q in result['questions']))
 def test_reply_cannot_precede_question(self):
  spec=self.spec();spec['documents'][1]['publishedAt']='2025-04-01'
  with self.assertRaises(ValueError):review(spec)
if __name__=='__main__':unittest.main()
