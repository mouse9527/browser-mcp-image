"""Smoke-test MCP client: every tool call on a NEW session, DELETE afterwards (like LiteLLM's MCP gateway)."""
import json, os, re, urllib.error, urllib.request

MCP = os.environ.get('MCP_URL', 'http://127.0.0.1:18931/mcp')
CDP = os.environ.get('CDP_URL', 'http://127.0.0.1:19222') + '/json/list'
SITE = os.environ.get('SITE_URL', 'http://127.0.0.1:18951/')


def _post(body, sid=None):
    h = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}
    if sid:
        h['Mcp-Session-Id'] = sid
    r = urllib.request.Request(MCP, data=json.dumps(body).encode(), headers=h, method='POST')
    try:
        with urllib.request.urlopen(r, timeout=180) as f:
            return f.status, f.read().decode(), f.headers.get('Mcp-Session-Id')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), None


def _parse(raw):
    for l in raw.splitlines():
        if l.startswith('data:') and l[5:].strip():
            m = json.loads(l[5:])
            if 'id' in m:
                return m
    return json.loads(raw) if raw.strip().startswith('{') else {}


def rpc(method, params):
    c, raw, sid = _post({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {
        'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'browser-mcp-smoke', 'version': '0'}}})
    _post({'jsonrpc': '2.0', 'method': 'notifications/initialized'}, sid)
    c, raw, _ = _post({'jsonrpc': '2.0', 'id': 2, 'method': method, 'params': params}, sid)
    m = _parse(raw) or {'error': {'http': c, 'body': raw[:200]}}
    if sid:
        urllib.request.urlopen(urllib.request.Request(MCP, method='DELETE', headers={'Mcp-Session-Id': sid}), timeout=10).close()
    return m


def call(name, args=None):
    """-> (is_error, text, images)"""
    m = rpc('tools/call', {'name': name, 'arguments': args or {}})
    res = m.get('result') or {}
    content = res.get('content') or []
    txt = '\n'.join(x.get('text', '') for x in content if x.get('type') == 'text')
    imgs = [x for x in content if x.get('type') == 'image']
    return bool(res.get('isError') or m.get('error')), txt or json.dumps(m.get('error')), imgs


def tabs():
    """ground truth: [(targetId[:6], url tail, title)] of real page targets"""
    return [(t['id'][:6], t['url'].replace(SITE, ''), t['title']) for t in json.load(urllib.request.urlopen(CDP)) if t['type'] == 'page']


def page_ids(list_pages_text):
    """'3: task-X (http://.../task.html?t=X)' -> {url_tail: id}; ids in list_pages output"""
    return {m.group(3).replace(SITE, ''): int(m.group(1))
            for m in re.finditer(r'^(\d+): (.*?) \((\S+)\)', list_pages_text, re.M)}


def short(t, n=160):
    return re.sub(r'\s+', ' ', t)[:n]
