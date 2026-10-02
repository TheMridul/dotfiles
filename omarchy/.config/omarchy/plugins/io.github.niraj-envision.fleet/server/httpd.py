"""Minimal HTTP + WebSocket server on the standard library.

Fleet ships no pip dependencies on purpose: it has to keep working after an
`archlinux-keyring` roll or a Python bump, on a machine whose whole point is
managing *other* machines. RFC 6455 is small enough to implement honestly.

The listener binds loopback only and every request carries a per-launch token,
so nothing on the LAN can drive your fleet.
"""
import base64
import hashlib
import json
import mimetypes
import math
import os
import socket
import socketserver
import struct
import threading
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

def log_exception(where):
    from logging import getLogger
    getLogger("fleet").exception(where)


GUID = b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# RFC 6455 section 1.3 test vector. A wrong byte here makes every handshake
# fail in a way that looks like a network problem from the browser side
# (onerror, then close code 1006, with a perfectly valid-looking 101 on the
# wire), so it is asserted at import rather than trusted.
assert base64.b64encode(
    hashlib.sha1(b"dGhlIHNhbXBsZSBub25jZQ==" + GUID).digest()
).decode() == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=", "WebSocket GUID is wrong"

OP_CONT, OP_TEXT, OP_BIN, OP_CLOSE, OP_PING, OP_PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA
MAX_JSON_BODY = 1024 * 1024
MAX_UPLOAD_BODY = 10 * 1024 * 1024 * 1024
MAX_WS_MESSAGE = 1024 * 1024
READ_TIMEOUT = 15


def _valid_json_shape(value, depth=0):
    if depth > 12:
        return False
    if isinstance(value, dict):
        return len(value) <= 128 and all(
            isinstance(k, str) and len(k) <= 256 and _valid_json_shape(v, depth + 1)
            for k, v in value.items())
    if isinstance(value, list):
        return len(value) <= 1024 and all(_valid_json_shape(v, depth + 1) for v in value)
    if isinstance(value, str):
        return len(value) <= 1024 * 1024
    if isinstance(value, float):
        return math.isfinite(value)
    return value is None or isinstance(value, (bool, int))


class WebSocket:
    """One upgraded connection. `send` is safe to call from any thread."""

    def __init__(self, conn):
        self.conn = conn
        self.closed = False
        self._wlock = threading.Lock()

    def send(self, data, opcode=None):
        if self.closed:
            return
        if isinstance(data, (dict, list)):
            data = json.dumps(data)
        if isinstance(data, str):
            data, opcode = data.encode(), opcode or OP_TEXT
        else:
            opcode = opcode or OP_BIN
        n = len(data)
        if n < 126:
            head = struct.pack("!BB", 0x80 | opcode, n)
        elif n < (1 << 16):
            head = struct.pack("!BBH", 0x80 | opcode, 126, n)
        else:
            head = struct.pack("!BBQ", 0x80 | opcode, 127, n)
        with self._wlock:
            try:
                self.conn.sendall(head + data)
            except OSError:
                self.closed = True

    def send_json(self, obj):
        self.send(json.dumps(obj), OP_TEXT)

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.conn.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("peer closed")
            buf += chunk
        return buf

    def recv(self):
        """Return (opcode, payload) or None on close. Reassembles fragments."""
        frags, frag_op = b"", None
        while True:
            b1, b2 = struct.unpack("!BB", self._recv_exact(2))
            fin, opcode = b1 & 0x80, b1 & 0x0F
            masked, length = b2 & 0x80, b2 & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            if length > MAX_WS_MESSAGE:
                raise ConnectionError("frame too large")
            mask = self._recv_exact(4) if masked else None
            payload = self._recv_exact(length) if length else b""
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))

            if opcode == OP_CLOSE:
                self.close()
                return None
            if opcode == OP_PING:
                self.send(payload, OP_PONG)
                continue
            if opcode == OP_PONG:
                continue
            if opcode == OP_CONT:
                if len(frags) + len(payload) > MAX_WS_MESSAGE:
                    raise ConnectionError("fragmented message too large")
                frags += payload
            else:
                frags, frag_op = payload, opcode
            if fin:
                return (frag_op, frags)

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            with self._wlock:
                self.conn.sendall(struct.pack("!BB", 0x80 | OP_CLOSE, 0))
        except OSError:
            pass
        try:
            self.conn.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass


class Raw:
    """A streamed response. `chunks` is any iterable of bytes.

    Downloads are piped straight from the remote `cat`/`tar` to the browser,
    so file size is bounded by the disk at each end rather than by RAM here.
    """

    def __init__(self, chunks, content_type="application/octet-stream",
                 filename=None, length=None):
        self.chunks = chunks
        self.content_type = content_type
        self.filename = filename
        self.length = length


class Router:
    """Tiny path router. Handlers get (handler, match_args, body) and return
    a JSON-serialisable object, or a (status, object) tuple."""

    def __init__(self):
        self.routes = []
        self.ws_routes = []

    def route(self, method, pattern):
        def deco(fn):
            self.routes.append((method, pattern.strip("/").split("/"), fn))
            return fn
        return deco

    def ws(self, pattern):
        def deco(fn):
            self.ws_routes.append((pattern.strip("/").split("/"), fn))
            return fn
        return deco

    @staticmethod
    def _match(parts, path_parts):
        if len(parts) != len(path_parts):
            return None
        args = []
        for p, v in zip(parts, path_parts):
            if p.startswith(":"):
                args.append(v)
            elif p != v:
                return None
        return args

    def find(self, method, path):
        pp = path.strip("/").split("/")
        for m, parts, fn in self.routes:
            if m != method:
                continue
            args = self._match(parts, pp)
            if args is not None:
                return fn, args
        return None, None

    def find_ws(self, path):
        pp = path.strip("/").split("/")
        for parts, fn in self.ws_routes:
            args = self._match(parts, pp)
            if args is not None:
                return fn, args
        return None, None


def make_handler(router, web_dir, token):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        _head_only = False
        server_version = "Fleet"
        sys_version = ""

        def log_message(self, fmt, *a):
            import os, sys
            if os.environ.get("FLEET_DEBUG"):
                sys.stderr.write("[req] %s\n" % (fmt % a)); sys.stderr.flush()

        # ------------------------------------------------------------ auth
        def _authorized(self, qs):
            if qs.get("t", [None])[0] == token:
                return True
            cookie = self.headers.get("Cookie") or ""
            return ("fleet_token=" + token) in cookie

        def _json(self, obj, status=200):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if not self._head_only:
                self.wfile.write(body)

        def _serve_static(self, path):
            rel = path.lstrip("/") or "index.html"
            # realpath on the *result*, not just the root: normpath alone still
            # lets a symlink inside web/ point anywhere on the filesystem.
            root = os.path.realpath(web_dir)
            full = os.path.realpath(os.path.join(root, rel))
            if full != root and not full.startswith(root + os.sep):
                return self._json({"error": "forbidden"}, 403)
            if os.path.isdir(full):
                full = os.path.join(full, "index.html")
            if not os.path.isfile(full):
                return self._json({"error": "not found", "path": rel}, 404)
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            with open(full, "rb") as fh:
                body = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            # The session token lives in the page URL, and terminals render
            # clickable links. Without this, following one would hand the token
            # to an external site in the Referer header.
            self.send_header("Referrer-Policy", "no-referrer")
            if rel == "index.html":
                # HttpOnly: the app authenticates with the ?t= parameter, so
                # nothing in the page needs to read this. It exists only so the
                # browser can fetch static assets, which carry no query string.
                self.send_header("Set-Cookie",
                                 "fleet_token=%s; Path=/; SameSite=Strict; HttpOnly"
                                 % token)
                self.send_header("Cache-Control", "no-store")
            else:
                self.send_header("Cache-Control", "max-age=300")
            self.end_headers()
            if not self._head_only:
                self.wfile.write(body)

        # --------------------------------------------------------- dispatch
        def _handle(self, method):
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            if not self._authorized(qs):
                return self._json({"error": "unauthorized"}, 401)

            if (self.headers.get("Upgrade") or "").lower() == "websocket":
                return self._upgrade(u.path, qs)

            if not u.path.startswith("/api/"):
                return self._serve_static(u.path) if method == "GET" else \
                    self._json({"error": "not found"}, 404)

            fn, args = router.find(method, u.path[4:])
            if not fn:
                return self._json({"error": "no route", "path": u.path}, 404)

            body = None
            lengths = self.headers.get_all("Content-Length") or []
            if len(lengths) > 1 or self.headers.get("Transfer-Encoding"):
                return self._json({"error": "ambiguous request framing"}, 400)
            try:
                n = int(lengths[0]) if lengths else 0
            except (TypeError, ValueError):
                return self._json({"error": "invalid Content-Length"}, 400)
            if n < 0:
                return self._json({"error": "invalid Content-Length"}, 400)
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
            if ctype == "application/octet-stream":
                if u.path != "/api/files/upload":
                    return self._json({"error": "binary body is not accepted here"}, 415)
                if not lengths or n > MAX_UPLOAD_BODY:
                    return self._json({"error": "upload length is missing or too large"}, 413)
                self.connection.settimeout(READ_TIMEOUT)
                # Leave the body on the socket; the route streams it itself.
                body = {"_stream": True, "_length": n}
            elif n:
                if ctype != "application/json":
                    return self._json({"error": "Content-Type must be application/json"}, 415)
                if n > MAX_JSON_BODY:
                    return self._json({"error": "JSON body exceeds 1 MiB"}, 413)
                self.connection.settimeout(READ_TIMEOUT)
                raw = self.rfile.read(n)
                if len(raw) != n:
                    return self._json({"error": "incomplete request body"}, 400)
                try:
                    body = json.loads(raw)
                except ValueError:
                    return self._json({"error": "malformed JSON"}, 400)
                if not isinstance(body, dict) or not _valid_json_shape(body):
                    return self._json({"error": "JSON body has invalid shape"}, 400)
            try:
                res = fn(self, args, body or {}, qs)
            except Exception as e:
                log_exception("api %s %s" % (method, u.path))
                payload = {"error": str(e)}
                if os.environ.get("FLEET_DEBUG"):
                    payload["trace"] = traceback.format_exc()[-1500:]
                return self._json(payload, 500)
            if isinstance(res, Raw):
                return self._stream(res)
            if isinstance(res, tuple):
                return self._json(res[1], res[0])
            return self._json(res if res is not None else {"ok": True})

        def _stream(self, raw):
            self.send_response(200)
            self.send_header("Content-Type", raw.content_type)
            if raw.filename:
                safe = raw.filename.replace('"', "").replace("\\", "")
                self.send_header("Content-Disposition",
                                 'attachment; filename="%s"' % safe)
            if raw.length is not None:
                self.send_header("Content-Length", str(raw.length))
                self.end_headers()
                try:
                    for c in raw.chunks:
                        self.wfile.write(c)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            # Unknown length (a tar of a directory): chunked transfer encoding.
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                for c in raw.chunks:
                    if not c:
                        continue
                    self.wfile.write(b"%x\r\n" % len(c) + c + b"\r\n")
                self.wfile.write(b"0\r\n\r\n")
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True

        def do_GET(self):
            self._handle("GET")

        def do_HEAD(self):
            # Answer HEAD like GET but suppress the body, so probes and health
            # checks get real headers instead of a 501.
            self._head_only = True
            try:
                self._handle("GET")
            finally:
                self._head_only = False

        def do_POST(self):
            self._handle("POST")

        def do_PUT(self):
            self._handle("PUT")

        def do_DELETE(self):
            self._handle("DELETE")

        # -------------------------------------------------------- upgrade
        def _same_origin(self):
            """WebSockets are exempt from CORS, so a page on another origin can
            open one against localhost. The token already stops that, but the
            check is one line and removes the whole class of attempt."""
            origin = self.headers.get("Origin")
            if not origin:
                return True          # non-browser client; the token still applies
            try:
                o = urlparse(origin).netloc.lower()
            except ValueError:
                return False
            return o == (self.headers.get("Host") or "").lower()

        def _upgrade(self, path, qs):
            if not self._same_origin():
                return self._json({"error": "cross-origin websocket refused"}, 403)
            fn, args = router.find_ws(path)
            if not fn:
                return self._json({"error": "no ws route"}, 404)
            import os as _os, sys as _sys
            if _os.environ.get("FLEET_DEBUG"):
                _sys.stderr.write("[ws] upgrade path=%s hdrs=%s\n" %
                    (path, dict(self.headers))); _sys.stderr.flush()
            key = self.headers.get("Sec-WebSocket-Key")
            if not key:
                return self._json({"error": "bad handshake"}, 400)
            accept = base64.b64encode(
                hashlib.sha1(key.encode() + GUID).digest()).decode()
            self.send_response(101, "Switching Protocols")
            self.send_header("Upgrade", "websocket")
            self.send_header("Connection", "Upgrade")
            self.send_header("Sec-WebSocket-Accept", accept)
            self.end_headers()
            self.wfile.flush()
            ws = WebSocket(self.connection)
            try:
                fn(ws, args, qs)
            except (ConnectionError, OSError):
                pass
            except Exception:
                log_exception("ws %s" % path)
            finally:
                ws.close()
            self.close_connection = True

    return Handler


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True
    # Terminals and the metrics stream each hold a connection for the life of
    # the window, so the default request-thread ceiling is far too low.
    request_queue_size = 128
    _request_slots = threading.BoundedSemaphore(64)

    def process_request(self, request, client_address):
        if not self._request_slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._request_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._request_slots.release()


class Server6(Server):
    address_family = socket.AF_INET6


def serve(router, web_dir, token, host="127.0.0.1", port=0):
    srv = Server((host, port), make_handler(router, os.path.realpath(web_dir), token))
    return srv


def serve_v6(router, web_dir, token, port, host="::1"):
    """Second listener on IPv6 loopback.

    `*.localhost` resolves to ::1 here, and a browser that picks IPv6 for a
    WebSocket while falling back to IPv4 for plain HTTP produces a baffling
    half-working app. Binding both keeps the two paths honest. Returns None if
    IPv6 is unavailable rather than refusing to start.
    """
    try:
        srv = Server6((host, port), make_handler(router, os.path.realpath(web_dir), token))
        return srv
    except OSError:
        return None
