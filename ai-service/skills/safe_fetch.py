"""Fetch a public web page without exposing internal networks (SSRF-safe).

Defenses:
  * Only http/https on ports 80/443, no credentials in the URL.
  * The hostname is resolved once and every resolved address must be a public
    unicast address. Loopback, private, link-local (including the cloud
    metadata endpoint 169.254.169.254), carrier-grade NAT, multicast, reserved
    and IPv4-mapped IPv6 forms of those are all rejected.
  * The connection goes to the validated IP, with the original hostname used
    for the Host header and TLS verification, so a second DNS answer cannot
    redirect the request (DNS rebinding).
  * Redirects are followed manually, at most MAX_REDIRECTS, and every hop is
    validated again.
  * Timeouts on connect and read, a response size cap, and a content-type
    allowlist.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable, Iterable
from urllib.parse import urljoin, urlsplit

ALLOWED_SCHEMES = {"http": 80, "https": 443}
ALLOWED_CONTENT_TYPES = {"text/html", "text/plain", "application/xhtml+xml"}
MAX_REDIRECTS = 3
MAX_BYTES = 2_000_000
TIMEOUT_SECONDS = 10.0
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
USER_AGENT = "JobApplicationCopilot/1.0 (+job posting fetcher)"


class FetchError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class Target:
    scheme: str
    hostname: str
    port: int
    path: str  # path plus query string
    ip: str


@dataclass
class RawResponse:
    status: int
    headers: dict[str, str]
    chunks: Iterable[bytes]


@dataclass
class FetchedPage:
    url: str
    content_type: str
    title: str | None
    text: str
    bytes_read: int
    redirects: int


Resolver = Callable[[str, int], list[str]]
Opener = Callable[[Target], RawResponse]


def system_resolver(hostname: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


def is_public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def resolve_target(url: str, resolver: Resolver) -> Target:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()

    if scheme not in ALLOWED_SCHEMES:
        raise FetchError("unsupported_scheme", f"Only http and https URLs are allowed, got '{scheme or 'none'}'")
    if parts.username or parts.password:
        raise FetchError("credentials_in_url", "URLs with credentials are not allowed")
    if not parts.hostname:
        raise FetchError("missing_host", "URL has no hostname")

    try:
        port = parts.port or ALLOWED_SCHEMES[scheme]
    except ValueError as error:
        raise FetchError("invalid_port", str(error)) from error
    if port not in ALLOWED_SCHEMES.values():
        raise FetchError("port_not_allowed", f"Port {port} is not allowed")

    try:
        addresses = resolver(parts.hostname, port)
    except (socket.gaierror, UnicodeError) as error:
        raise FetchError("dns_failed", f"Could not resolve {parts.hostname}") from error
    if not addresses:
        raise FetchError("dns_failed", f"Could not resolve {parts.hostname}")

    # Reject if *any* answer is internal, so round-robin DNS cannot sneak one in.
    blocked = [address for address in addresses if not is_public_address(address)]
    if blocked:
        raise FetchError("blocked_address", f"{parts.hostname} resolves to a non-public address")

    path = parts.path or "/"
    if parts.query:
        path += f"?{parts.query}"

    return Target(scheme=scheme, hostname=parts.hostname, port=port, path=path, ip=addresses[0])


def urllib3_opener(target: Target) -> RawResponse:
    import certifi
    import urllib3

    timeout = urllib3.Timeout(connect=TIMEOUT_SECONDS, read=TIMEOUT_SECONDS)
    common = dict(port=target.port, timeout=timeout, retries=False, maxsize=1)

    if target.scheme == "https":
        pool = urllib3.HTTPSConnectionPool(
            target.ip,
            server_hostname=target.hostname,
            assert_hostname=target.hostname,
            cert_reqs="CERT_REQUIRED",
            ca_certs=certifi.where(),
            **common,
        )
    else:
        pool = urllib3.HTTPConnectionPool(target.ip, **common)

    default_port = ALLOWED_SCHEMES[target.scheme]
    host_header = target.hostname if target.port == default_port else f"{target.hostname}:{target.port}"
    response = pool.urlopen(
        "GET",
        target.path,
        headers={"Host": host_header, "User-Agent": USER_AGENT, "Accept": "text/html,text/plain;q=0.9"},
        redirect=False,
        preload_content=False,
        decode_content=True,
    )
    return RawResponse(
        status=response.status,
        headers={key.lower(): value for key, value in response.headers.items()},
        chunks=response.stream(64 * 1024),
    )


def read_capped(chunks: Iterable[bytes], limit: int) -> bytes:
    body = bytearray()
    for chunk in chunks:
        body.extend(chunk)
        if len(body) > limit:
            raise FetchError("too_large", f"Response is larger than {limit} bytes")
    return bytes(body)


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "head"}
    BLOCK = {"p", "div", "li", "ul", "ol", "br", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "tr", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title: str | None = None
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True
        elif tag in self.SKIP:
            self._skip_depth += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data
        elif not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> tuple[str | None, str]:
    parser = _TextExtractor()
    parser.feed(html)
    lines = (" ".join(line.split()) for line in "".join(parser.parts).splitlines())
    text = "\n".join(line for line in lines if line)
    title = " ".join(parser.title.split()) if parser.title else None
    return title, text


def fetch_page(url: str, resolver: Resolver = system_resolver, opener: Opener = urllib3_opener) -> FetchedPage:
    current = url
    for redirects in range(MAX_REDIRECTS + 1):
        target = resolve_target(current, resolver)
        try:
            response = opener(target)
        except FetchError:
            raise
        except Exception as error:
            raise FetchError("connection_failed", f"Could not fetch {target.hostname}: {type(error).__name__}") from error

        if response.status in REDIRECT_STATUSES:
            location = response.headers.get("location")
            if not location:
                raise FetchError("bad_redirect", "Redirect without a Location header")
            current = urljoin(current, location)
            continue

        if response.status != 200:
            raise FetchError("http_error", f"Server returned HTTP {response.status}")

        content_type_header = response.headers.get("content-type", "")
        content_type = content_type_header.split(";")[0].strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise FetchError("unsupported_content_type", f"Content type '{content_type or 'unknown'}' is not supported")

        body = read_capped(response.chunks, MAX_BYTES)
        charset = "utf-8"
        if "charset=" in content_type_header:
            charset = content_type_header.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            decoded = body.decode(charset, errors="replace")
        except LookupError:
            decoded = body.decode("utf-8", errors="replace")

        if content_type == "text/plain":
            title, text = None, decoded.strip()
        else:
            title, text = html_to_text(decoded)

        return FetchedPage(
            url=current, content_type=content_type, title=title, text=text, bytes_read=len(body), redirects=redirects
        )

    raise FetchError("too_many_redirects", f"More than {MAX_REDIRECTS} redirects")
