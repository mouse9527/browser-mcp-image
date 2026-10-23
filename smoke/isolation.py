"""Two tasks X / Y interleaved, each only on its own pageId; every call = new session. Exit 1 unless all steps pass."""
import json, re, struct, base64
from mcpclient import call, tabs, page_ids, short, SITE

RES = []


def step(desc, r, check=None):
    err, txt, imgs = r
    truth = tabs()
    ok = (not err) if check is None else check(err, txt, imgs, truth)
    RES.append(ok)
    print(json.dumps({'ok': ok, 'do': desc, 'error': err, 'reply': short(txt), 'cdp': truth}, ensure_ascii=False), flush=True)
    return txt, imgs


def pid_from(txt, tail):
    return page_ids(txt).get(tail)


def title(truth, tail):
    return next((t for _, u, t in truth if u == tail), None)


def uid(snapshot, label):
    m = re.search(r'uid=(\S+) button "%s"' % re.escape(label), snapshot)
    return m.group(1) if m else None


# --- each task opens its own page (background: does not steal focus)
tx, _ = step('X new_page task.html?t=X (background)', call('new_page', {'url': SITE + 'task.html?t=X', 'background': True}))
X = pid_from(tx, 'task.html?t=X')
ty, _ = step('Y new_page task.html?t=Y (background)', call('new_page', {'url': SITE + 'task.html?t=Y', 'background': True}))
Y = pid_from(ty, 'task.html?t=Y')
print(json.dumps({'pageIds': {'X': X, 'Y': Y}}))
# --- 2. interleaved
step('X navigate own page -> t=X2', call('navigate_page', {'pageId': X, 'type': 'url', 'url': SITE + 'task.html?t=X2'}),
     lambda e, t, i, tr: not e and title(tr, 'task.html?t=X2') == 'task-X2' and title(tr, 'task.html?t=Y') == 'task-Y')
step('Y navigate own page -> t=Y2', call('navigate_page', {'pageId': Y, 'type': 'url', 'url': SITE + 'task.html?t=Y2'}),
     lambda e, t, i, tr: not e and title(tr, 'task.html?t=Y2') == 'task-Y2' and title(tr, 'task.html?t=X2') == 'task-X2')
sx, _ = step('X take_snapshot own page', call('take_snapshot', {'pageId': X}), lambda e, t, i, tr: not e and 'Task X2' in t and 'Task Y2' not in t)
ux = uid(sx, 'Normal button')
sy, _ = step('Y take_snapshot own page', call('take_snapshot', {'pageId': Y}), lambda e, t, i, tr: not e and 'Task Y2' in t)
uy = uid(sy, 'Normal button')
step(f'Y click own button uid={uy}', call('click', {'pageId': Y, 'uid': uy}),
     lambda e, t, i, tr: not e and title(tr, 'task.html?t=Y2') == 'task-Y2-clicked' and title(tr, 'task.html?t=X2') == 'task-X2')
# --- 3. X's uid taken BEFORE Y snapshot / Y click, used in a later session
step(f'X click own button with uid={ux} from its earlier snapshot (Y snapshotted since)', call('click', {'pageId': X, 'uid': ux}),
     lambda e, t, i, tr: not e and title(tr, 'task.html?t=X2') == 'task-X2-clicked')
step(f'X click with Y\'s uid={uy} on X\'s page (cross-task uid)', call('click', {'pageId': X, 'uid': uy}),
     lambda e, t, i, tr: e or title(tr, 'task.html?t=Y2') == 'task-Y2-clicked')  # either refused or acts on X only
# --- 4. click_at: CSS px in viewport? button #at is at left 100 top 200 (120x40)
step('X click_at (160,220) on own page', call('click_at', {'pageId': X, 'x': 160, 'y': 220}),
     lambda e, t, i, tr: not e and title(tr, 'task.html?t=X2') == 'at-160x220' and title(tr, 'task.html?t=Y2') == 'task-Y2-clicked')
_, imgs = step('Y take_screenshot own page', call('take_screenshot', {'pageId': Y}), lambda e, t, i, tr: not e and bool(i))
if imgs:
    raw = base64.b64decode(imgs[0]['data'])
    w, h = (struct.unpack('>II', raw[16:24]) if raw[:4] == b'\x89PNG' else (None, None))
    print(json.dumps({'screenshot': {'mime': imgs[0].get('mimeType'), 'png_size': [w, h]}}))
# --- select_page must not matter; page tools without pageId must fail
step('X select_page own page (bringToFront)', call('select_page', {'pageId': X, 'bringToFront': True}))
step('Y click_at (160,220) on own page right after X selected its page', call('click_at', {'pageId': Y, 'x': 160, 'y': 220}),
     lambda e, t, i, tr: not e and title(tr, 'task.html?t=Y2') == 'at-160x220' and title(tr, 'task.html?t=X2') == 'at-160x220')
for tool, args in (('take_snapshot', {}), ('click_at', {'x': 1, 'y': 1}), ('navigate_page', {'type': 'url', 'url': SITE + 'task.html?t=Z'}),
                   ('evaluate_script', {'function': '() => 1'})):
    step(f'{tool} WITHOUT pageId -> must error', call(tool, args), lambda e, t, i, tr: e)
# --- X stale uid after its page navigated again
step('X navigate own page -> t=X3', call('navigate_page', {'pageId': X, 'type': 'url', 'url': SITE + 'task.html?t=X3'}))
step(f'X click with stale uid={ux} (page navigated since)', call('click', {'pageId': X, 'uid': ux}), lambda e, t, i, tr: True)
# --- X closes only its own page
step('X close_page own page', call('close_page', {'pageId': X}),
     lambda e, t, i, tr: not e and title(tr, 'task.html?t=X3') is None and title(tr, 'task.html?t=Y2') == 'at-160x220'
     and title(tr, 'user.html') == 'user-own-page')
step('Y take_snapshot own page after X closed its page', call('take_snapshot', {'pageId': Y}), lambda e, t, i, tr: not e and 'Task Y2' in t)
print('SUMMARY %d/%d' % (sum(RES), len(RES)))
raise SystemExit(0 if all(RES) else 1)
