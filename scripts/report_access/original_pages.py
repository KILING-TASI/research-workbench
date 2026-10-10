"""Small per-run original-page cache. No acquisition, OCR, or persistent data store."""
import hashlib,io
from pathlib import Path

class InRunPDFPages:
    def __init__(self,max_bytes=128*1024*1024):
        self.max_bytes=max_bytes;self.used_bytes=0;self.readers={};self.texts={}
    def quote_status(self,path,sha256,physical_page,quote):
        path=Path(path).resolve();key=(str(path),sha256)
        if isinstance(physical_page,bool) or not isinstance(physical_page,int) or physical_page<1:raise ValueError('需明确正整数物理页')
        if not isinstance(quote,str) or not quote.strip():raise ValueError('原文引句缺失')
        if key not in self.readers:
            if not path.is_file() or path.stat().st_size>64*1024*1024:raise ValueError('指定原文缺失或过大')
            size=path.stat().st_size
            if self.used_bytes+size>self.max_bytes:raise ValueError('本次原文缓存过大，请缩小或分批核对')
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=sha256:raise ValueError('指定原文摘要不符')
            self.used_bytes+=len(raw)
            try:from pypdf import PdfReader
            except ImportError:self.readers[key]=None
            else:self.readers[key]=PdfReader(io.BytesIO(raw))
        reader=self.readers[key]
        if reader is None:return 'pdf-component-missing'
        if physical_page>len(reader.pages):raise ValueError('原文物理页超界')
        page_key=(key,physical_page)
        if page_key not in self.texts:self.texts[page_key]=''.join((reader.pages[physical_page-1].extract_text() or '').split())
        return 'quote-found-on-page' if ''.join(quote.split()) in self.texts[page_key] else 'quote-not-found'
