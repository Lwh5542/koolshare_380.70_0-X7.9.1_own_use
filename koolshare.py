from flask import Flask, request, Response, abort, send_from_directory
import os, re, json, hashlib

app = Flask(__name__)

BASE = os.path.dirname(os.path.abspath(__file__))
PICTURE_DIR = os.path.join(BASE, 'picture')   # 图标所在目录
FILE_DIR    = os.path.join(BASE, 'file')      # 包文件所在目录
APP_RESP    = os.path.join(BASE, 'app_response.txt')

CB_SAFE    = re.compile(r'^[0-9A-Za-z_\.\[\]\$]+$')
JSONP_HEAD = re.compile(r'^\s*([0-9A-Za-z_\.\[\]\$]+)\s*\(' , re.S)

# 严格的文件名和模块名验证
SAFE_FILENAME = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_\-]*\.tar\.gz$')
SAFE_MODULE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_\-]*$')

# -------------------- 通用：读取文本+JSONP封装 --------------------

def load_text(name: str) -> str:
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        abort(404, f'missing file: {name}')
    with open(p, 'r', encoding='utf-8') as f:
        return f.read()

def make_jsonp(content: str, callback: str) -> str:
    # 已是 JSONP：只改回调名，不再二次包装
    if JSONP_HEAD.match(content):
        if callback:
            content = JSONP_HEAD.sub(f'{callback}(', content, count=1)
        # 保证以 ');' 结尾
        return content if content.rstrip().endswith(');') else (content.rstrip() + ');')
    # 纯 JSON：按需包一层
    if callback:
        return f'{callback}({content});'
    return content

def reply_from(file_name: str) -> Response:
    raw = load_text(file_name)
    cb = (request.args.get('callback') or '').strip()
    if cb and not CB_SAFE.match(cb):
        return Response('/* invalid callback */', status=400, mimetype='application/javascript')
    body = make_jsonp(raw, cb)
    return Response(body, mimetype='application/javascript; charset=utf-8')

# -------------------- 新增：MD5 计算 & app_response.txt 自动更新 --------------------

def _md5_of(path: str, chunk_size: int = 1024 * 1024) -> str:
    md5 = hashlib.md5()
    with open(path, 'rb') as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            md5.update(b)
    return md5.hexdigest()

def _map_tarurl_to_local(tar_url: str) -> str | None:
    """
    把 JSON 里的 tar_url 映射为本地真实文件：
      优先 file/<module>/<name>.tar.gz
      其次 file/<name>.tar.gz
    """
    # 防止路径遍历攻击
    if '..' in tar_url or tar_url.startswith('/') or '//' in tar_url:
        return None
    
    rel = tar_url.strip('/').replace('/', os.sep)
    rel = os.path.normpath(rel).lstrip(os.sep)
    
    # 检查是否试图跳出目标目录
    if rel.startswith('..') or os.sep + '..' in rel:
        return None
    
    p1 = os.path.join(FILE_DIR, rel)
    if os.path.isfile(p1) and p1.startswith(FILE_DIR):
        return p1
    
    p2 = os.path.join(FILE_DIR, os.path.basename(rel))
    if os.path.isfile(p2) and p2.startswith(FILE_DIR):
        return p2
    
    return None

def _parse_jsonp(text: str) -> tuple[str | None, dict]:
    """
    解析 JSONP/JSON：
      返回 (callback_name | None, json_obj)
    """
    m = JSONP_HEAD.match(text)
    payload = text
    cb = None
    if m:
        cb = m.group(1)
        left = text.find('(')
        payload = text[left+1:].strip()
        if payload.endswith(');'):
            payload = payload[:-2].rstrip()
    data = json.loads(payload)
    return cb, data

def _dump_with_jsonp(cb: str | None, data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return f'{cb}({payload});' if cb else payload

def update_app_response_md5s() -> None:
    """
    扫描 file/ 目录，对 app_response.txt 中的 apps[*].md5 以及顶层 md5 进行更新。
    仅当本地文件存在时才更新；保持回调名与 JSONP 外壳不变；原地覆盖写回。
    """
    if not os.path.exists(APP_RESP):
        # print('[md5] app_response.txt not found, skip')
        return

    try:
        original = load_text('app_response.txt')
    except Exception as e:
        # print(f'[md5] read app_response.txt failed: {e!r}')
        return

    try:
        cb, data = _parse_jsonp(original)
    except Exception as e:
        # print(f'[md5] parse app_response.txt failed: {e!r}')
        return

    changed = False

    # 更新 apps 列表
    apps = data.get('apps', [])
    for app_item in apps:
        tar_url = app_item.get('tar_url')
        if not tar_url:
            continue
        local = _map_tarurl_to_local(tar_url)
        if not local:
            continue
        try:
            new_md5 = _md5_of(local)
            if app_item.get('md5') != new_md5:
                # print(f"[md5] {tar_url} -> {new_md5}")
                app_item['md5'] = new_md5
                changed = True
        except Exception as e:
            # print(f"[md5] calc failed for {tar_url}: {e!r}")
            pass

    # 更新顶层 tar_url/md5（若存在且文件存在）
    top_tar = data.get('tar_url')
    if top_tar:
        top_local = _map_tarurl_to_local(top_tar)
        if top_local:
            try:
                top_md5 = _md5_of(top_local)
                if data.get('md5') != top_md5:
                    # print(f"[md5] top-level {top_tar} -> {top_md5}")
                    data['md5'] = top_md5
                    changed = True
            except Exception as e:
                # print(f"[md5] calc failed for top-level {top_tar}: {e!r}")
                pass

    if not changed:
        # print('[md5] no changes')
        return

    new_text = _dump_with_jsonp(cb, data)
    tmp = APP_RESP + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(new_text)
        os.replace(tmp, APP_RESP)
        # print('[md5] app_response.txt updated')
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

# 脚本启动时自动更新MD5
try:
    update_app_response_md5s()
except Exception as e:
    # print(f'[md5] startup update failed: {e!r}')
    pass

# -------------------- 业务路由 --------------------

@app.route('/softcenter/app.json.js')
def app_js():
    return reply_from('app_response.txt')

@app.route('/softcenter/push_message.json.js')
def push_js():
    return reply_from('push_response.txt')

# 只允许 .png 的静态图标：/softcenter/softcenter/res/<filename>.png
@app.route('/softcenter/softcenter/res/<path:filename>')
def softcenter_res(filename):
    filename = os.path.basename(filename)  # 防路径穿越
    if os.path.splitext(filename)[1].lower() != '.png':
        abort(404)
    file_path = os.path.join(PICTURE_DIR, filename)
    if not os.path.isfile(file_path):
        abort(404)
    resp = send_from_directory(PICTURE_DIR, filename)
    resp.cache_control.no_cache = True
    resp.cache_control.no_store = True
    resp.cache_control.max_age = 0
    return resp

# 根据 module 和 filename 返回 file 文件夹中的 tar.gz 文件（加强路径验证）
@app.route('/<module>/<filename>')
def serve_file(module, filename):
    # 严格验证模块名和文件名
    if not (SAFE_MODULE.match(module) and SAFE_FILENAME.match(filename)):
        abort(404)
    
    # 防止路径遍历
    filename = os.path.basename(filename)
    
    # 先找 file/<name>.tar.gz（你当前 acme.tar.gz 就是这种）
    direct_path = os.path.join(FILE_DIR, filename)
    if os.path.isfile(direct_path) and direct_path.startswith(FILE_DIR):
        return send_from_directory(FILE_DIR, filename, as_attachment=True)

    # 再找 file/<module>/<name>.tar.gz（兼容将来分模块）
    module_dir = os.path.join(FILE_DIR, module)
    if not module_dir.startswith(FILE_DIR):  # 额外安全检查
        abort(404)
    
    module_path = os.path.join(module_dir, filename)
    if os.path.isfile(module_path) and module_path.startswith(FILE_DIR):
        return send_from_directory(module_dir, filename, as_attachment=True)

    abort(404)
