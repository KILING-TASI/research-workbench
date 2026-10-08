import unittest
from unittest.mock import patch
import portable_collect as p
class Response:
 def __init__(self,body):self.body=body;self.requested=None
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,n):self.requested=n;return self.body[:n]
class PortableResponseBoundary(unittest.TestCase):
 def test_success_decoded_with_bounded_read(self):
  r=Response('基金'.encode('utf-8'))
  with patch.object(p.urllib.request,'urlopen',return_value=r):self.assertEqual(p.get('https://example.org'),'基金')
  self.assertEqual(r.requested,p.MAX_RESPONSE_BYTES+1)
 def test_oversize_not_silently_truncated(self):
  r=Response(b'x'*(p.MAX_RESPONSE_BYTES+1))
  with patch.object(p.urllib.request,'urlopen',return_value=r),self.assertRaisesRegex(ValueError,'超过16MiB'):p.get('https://example.org')
 def test_exact_boundary_accepted(self):
  r=Response(b'x'*p.MAX_RESPONSE_BYTES)
  with patch.object(p.urllib.request,'urlopen',return_value=r):self.assertEqual(len(p.get('https://example.org')),p.MAX_RESPONSE_BYTES)
 def test_invalid_encoding_not_replaced(self):
  with patch.object(p.urllib.request,'urlopen',return_value=Response(b'\xff')),self.assertRaises(UnicodeDecodeError):p.get('https://example.org')
