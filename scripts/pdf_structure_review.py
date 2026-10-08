"""PDF structure observations, not document authenticity or content completeness."""
import hashlib,logging
from pathlib import Path
from pypdf import PdfReader

def review(path):
 p=Path(path);raw=p.read_bytes();warnings=[]
 class Capture(logging.Handler):
  def emit(self,record):warnings.append(record.getMessage())
 logger=logging.getLogger('pypdf');handler=Capture();logger.addHandler(handler)
 last_eof=raw.rfind(b'%%EOF');trailing=raw[last_eof+5:] if last_eof>=0 else b''
 result=dict(lastEOFMarkerOffset=last_eof,nonWhitespaceBytesAfterLastEOF=len(trailing.strip()),sha256=hashlib.sha256(raw).hexdigest(),pdfSignature=raw.startswith(b'%PDF-'),eofMarkerInTail=b'%%EOF' in raw[-4096:])
 try:
  doc=PdfReader(p,strict=True);result.update(strictStructureRead='readable',pageCount=len(doc.pages))
 except Exception as e:result.update(strictStructureRead='failed',reason=type(e).__name__+': '+str(e))
 finally:logger.removeHandler(handler)
 result['warnings']=warnings;result['reviewRequired']=not result['pdfSignature'] or not result['eofMarkerInTail'] or result['strictStructureRead']!='readable' or bool(warnings) or bool(trailing.strip());result['scope']='签名、尾标记和严格结构读取；不是原件官方认证或完整内容核验'
 return result
