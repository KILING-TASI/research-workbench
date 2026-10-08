"""Bounded public HTTPS downloads; validate every redirect before connecting."""
import ipaddress
import http.client
import socket
import re
import math
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, ProxyHandler, Request, build_opener


def public_connection(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    """Connect to the checked IP itself, avoiding a second hostname resolution."""
    host, port = address
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('拒绝回环、私网及非公开下载地址')
    error = None
    for family, kind, protocol, _, target in addresses:
        connection = socket.socket(family, kind, protocol)
        try:
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                connection.settimeout(timeout)
            if source_address: connection.bind(source_address)
            connection.connect(target)
            return connection
        except OSError as exc:
            error = exc
            connection.close()
    raise error or OSError('无法连接公开下载地址')


class PublicHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        self._create_connection = public_connection
        super().connect()


class PublicHTTPSHandler(HTTPSHandler):
    def https_open(self, request):
        return self.do_open(PublicHTTPSConnection, request, context=self._context)


def validate_url(url):
    if not isinstance(url,str) or re.search(r'[\s\x00-\x1f\x7f]',url):raise ValueError('下载URL须为无空白或控制字符的字符串')
    parts = urlsplit(url)
    if parts.scheme != 'https' or not parts.hostname or parts.username is not None or parts.password is not None:
        raise ValueError('下载仅接受无凭据的公开 HTTPS 地址')
    if parts.port not in (None, 443):
        raise ValueError('下载仅接受 HTTPS 标准端口')
    addresses = socket.getaddrinfo(parts.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('拒绝回环、私网及非公开下载地址')
    return url


def check_host(url, allowed_hosts):
    if allowed_hosts is not None and urlsplit(url).hostname not in allowed_hosts:
        raise ValueError('下载来源域名不在允许范围')

class PublicRedirect(HTTPRedirectHandler):
    def __init__(self, allowed_hosts=None):
        super().__init__()
        self.allowed_hosts = allowed_hosts
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_host(newurl, self.allowed_hosts)
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, limit=30 * 1024 * 1024, timeout=30, headers=None, allowed_hosts=None, return_metadata=False):
    if type(limit) is not int or limit<=0:raise ValueError('下载容量限制须为正整数')
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or timeout<=0:raise ValueError('下载超时须为正有限秒数')
    if allowed_hosts is not None and (not isinstance(allowed_hosts,(list,tuple,set,frozenset)) or not allowed_hosts or any(not isinstance(h,str) or not h for h in allowed_hosts)):raise ValueError('允许域名须为非空文本集合')
    check_host(url,allowed_hosts)
    validate_url(url)
    request = Request(url, headers=headers or {'User-Agent': 'Mozilla/5.0'})
    # Do not silently route public downloads through an environment-defined proxy.
    with build_opener(ProxyHandler({}), PublicHTTPSHandler(), PublicRedirect(allowed_hosts)).open(request, timeout=timeout) as response:
        resolved = response.geturl()
        check_host(resolved,allowed_hosts)
        validate_url(resolved)
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('下载超过容量限制')
    return {'raw':raw,'resolvedUrl':resolved} if return_metadata else raw
