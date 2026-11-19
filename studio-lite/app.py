"""GRSlot Studio Lite — local Film Library and six-slot project editor."""
import argparse
import base64
from contextlib import contextmanager
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import re
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import ProxyHandler, build_opener
import webbrowser
import zlib

ROOT = Path(__file__).resolve().parent
DEFAULT_LIBRARY = ROOT.parent / "assets/library.json"
DEFAULT_ICON = ROOT.parent / "assets/icons/ui/category-all/icon.rgba"
INSTANCE_ID = hashlib.sha256(os.fsencode(ROOT)).hexdigest()
CATEGORIES = {'kodak': 'Kodak', 'fujifilm': 'Fujifilm', 'digital': 'Digital', 'bw': '黑白', 'other': '其他', 'my-luts': '自定义'}
GROUPS = {'spk': 'Spektrafilm', 'spec': 'Spectral', 'user-import': '自定义'}


class ProjectError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def require(condition, message):
    if not condition:
        raise ProjectError(message)


def png_chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def rgba_png(raw):
    require(len(raw) == 6400, '胶片图标必须是 40×40 RGBA。')
    rows = b''.join(b'\0' + raw[y * 160:(y + 1) * 160] for y in range(40))
    return b'\x89PNG\r\n\x1a\n' + png_chunk(b'IHDR', struct.pack('>IIBBBBB', 40, 40, 8, 6, 0, 0, 0)) + png_chunk(b'IDAT', zlib.compress(rows)) + png_chunk(b'IEND', b'')


def validate_icon(value):
    require(type(value) is str and value.startswith('data:image/png;base64,'), '请使用 PNG 图标。')
    try:
        data = base64.b64decode(value.split(',', 1)[1], validate=True)
    except (ValueError, base64.binascii.Error):
        raise ProjectError('图标数据无效。') from None
    require(len(data) <= 20000 and data[:8] == b'\x89PNG\r\n\x1a\n', '图标数据无效或过大。')
    position, kinds, compressed = 8, [], bytearray()
    while position < len(data):
        require(position + 12 <= len(data), 'PNG 图标不完整。')
        length = struct.unpack_from('>I', data, position)[0]
        end = position + 12 + length
        require(end <= len(data), 'PNG 图标不完整。')
        kind, content = data[position + 4:position + 8], data[position + 8:end - 4]
        require(kind in (b'IHDR', b'IDAT', b'IEND') and zlib.crc32(kind + content) == struct.unpack_from('>I', data, end - 4)[0], 'PNG 图标格式无效。')
        if kind == b'IHDR':
            require(not kinds and content == struct.pack('>IIBBBBB', 40, 40, 8, 6, 0, 0, 0), '请使用 40×40 RGBA 图标。')
        if kind == b'IDAT':
            require(kinds and kinds[-1] in (b'IHDR', b'IDAT'), 'PNG 图标顺序无效。')
            compressed.extend(content)
        kinds.append(kind)
        position = end
        if kind == b'IEND':
            require(length == 0 and end == len(data), 'PNG 图标结尾无效。')
            break
    require(kinds and kinds[0] == b'IHDR' and kinds[-1] == b'IEND' and b'IDAT' in kinds, 'PNG 图标缺少内容。')
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, 6441)
    except zlib.error:
        raise ProjectError('PNG 图标压缩数据无效。') from None
    require(len(raw) == 6440 and decoder.eof and not decoder.unused_data and all(raw[y * 161] <= 4 for y in range(40)), 'PNG 图标像素数据无效。')
    return value


class Studio:
    def __init__(self, library_path, data_dir):
        self.library_path = Path(library_path).resolve()
        raw = self.library_path.read_bytes()
        library = json.loads(raw)
        self.library_id = hashlib.sha256(raw).hexdigest()
        self.data_dir = Path(data_dir).resolve()
        self.project_path = self.data_dir / 'project.json'
        self.lock = threading.Lock()
        self.films, self.icons = [], {}
        package = self.library_path.parent
        if package.name == 'assets':
            package = package.parent
        for source in library['films']:
            uid = source['uid']
            require(type(uid) is int and uid not in self.icons, '胶片库存在重复或无效 UID。')
            icon_name = source.get('icon')
            icon = (package / icon_name).resolve() if icon_name else DEFAULT_ICON
            require(not icon_name or icon.is_relative_to(package), '图标路径超出胶片项目目录。')
            require(icon.is_file(), f'胶片 UID {uid} 缺少图标。')
            self.icons[uid] = icon
            group = {'MIT': 'spec', 'CC-BY-SA-4.0': 'spk'}.get(source.get('license'), 'user-import')
            self.films.append(dict(uid=uid, name=source['name'],
                                   category=source.get('category', 'other'), group=group,
                                   author=source.get('author', 'Unknown'),
                                   colour_files=source.get('files', {})))
        self.ids = {f['uid'] for f in self.films}
        self.defaults = library['defaults']
        require(len(self.defaults) == 6 and set(self.defaults) <= self.ids, '胶片库的六槽默认分配无效。')
        self.original = dict(schema=1, library_id=self.library_id, selected=library.get('selected', [f['uid'] for f in self.films]), overrides={}, slots=list(self.defaults), revision=0)
        self.validate(self.original)

    def validate(self, project):
        require(type(project) is dict and set(project) == {'schema', 'library_id', 'selected', 'overrides', 'slots', 'revision'}, '项目字段无效。')
        require(type(project['schema']) is int and project['schema'] == 1 and project['library_id'] == self.library_id, '项目与当前胶片库不匹配。')
        selected, slots, overrides = project['selected'], project['slots'], project['overrides']
        require(type(selected) is list and all(type(uid) is int for uid in selected), '胶片选择无效。')
        require(len(set(selected)) == len(selected) and set(selected) <= self.ids, '胶片选择包含重复或未知 UID。')
        require(type(slots) is list and len(slots) == 6 and all(type(uid) is int and uid in selected for uid in slots), '六槽必须分配已勾选的胶片。')
        require(type(project['revision']) is int and project['revision'] >= 0, '项目版本无效。')
        require(type(overrides) is dict and set(overrides) <= {str(uid) for uid in self.ids}, '胶片资料包含未知 UID。')
        for values in overrides.values():
            require(type(values) is dict and set(values) <= {'name', 'category', 'icon', 'notes', 'icon_design'}, '胶片资料字段无效。')
            if 'name' in values:
                name = values['name']
                require(type(name) is str and name == name.strip() and 1 <= len(name) <= 32 and all(32 <= ord(c) < 127 for c in name), '名称需为 1–32 个英文、数字或常用英文符号。')
            if 'category' in values:
                require(type(values['category']) is str and values['category'] in CATEGORIES, '胶片分类无效。')
            if 'notes' in values:
                notes = values['notes']
                require(type(notes) is str and len(notes) <= 4000 and not any(0xD800 <= ord(c) <= 0xDFFF for c in notes), '备注须为有效文字，最多 4000 字符。')
            if 'icon_design' in values:
                design = values['icon_design']
                colors = {'topInk', 'topFill', 'smallInk', 'mainInk', 'bodyFill', 'dividerFill', 'stripFill'}
                require('icon' in values and type(design) is dict and set(design) == colors | {'brand', 'small', 'main', 'divider', 'strip'}, '自定义图标设置无效。')
                for key, minimum, maximum in [('brand', 1, 10), ('small', 0, 10), ('main', 1, 6)]:
                    value = design[key]
                    require(type(value) is str and value == value.strip() and minimum <= len(value) <= maximum and re.fullmatch(r'[A-Za-z0-9 .&+\-]*', value), '图标文字格式无效。')
                require(all(type(design[key]) is str and re.fullmatch(r'#[0-9A-Fa-f]{6}', design[key]) for key in colors), '图标颜色无效。')
                require(all(type(design[key]) is bool for key in ('divider', 'strip')), '图标色条设置无效。')
            if 'icon' in values:
                validate_icon(values['icon'])
        return project

    def read(self):
        if not self.project_path.exists():
            return json.loads(json.dumps(self.original))
        try:
            return self.validate(json.loads(self.project_path.read_text()))
        except (OSError, ValueError) as error:
            raise ProjectError('已保存项目无法读取，请保留文件并检查。' + str(error), 409) from error

    @contextmanager
    def write_lock(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with self.lock, (self.data_dir / 'project.lock').open('a') as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)

    def save(self, project):
        self.validate(project)
        with self.write_lock():
            current = self.read()
            if current['revision'] != project['revision']:
                raise ProjectError('项目已在另一个页面更新。请重新打开页面后继续。', 409)
            saved = dict(project, revision=current['revision'] + 1)
            fd, temporary = tempfile.mkstemp(prefix='.project-', dir=self.data_dir)
            try:
                with os.fdopen(fd, 'w') as output:
                    json.dump(saved, output, ensure_ascii=False, indent=2)
                    output.flush()
                    os.fsync(output.fileno())
                os.replace(temporary, self.project_path)
            finally:
                Path(temporary).unlink(missing_ok=True)
            return saved

    def response(self):
        return dict(films=self.films, categories=CATEGORIES, groups=GROUPS, project=self.read(), saved=self.project_path.exists(),
                    project_path=str(self.project_path))


def make_server(studio, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, status, data, content_type='application/json; charset=utf-8'):
            if isinstance(data, (dict, list)):
                data = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(data)

        def dispatch(self):
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            require(self.headers.get('Host') in allowed, '请求来源无效。')
            require(self.headers.get('Origin') in (None, *['http://' + host for host in allowed]), '请求来源无效。')
            if self.command == 'POST':
                require(self.headers.get('X-GRSlot-Client') == 'studio-lite', '请求无效。')
                require(self.path == '/api/project', '保存请求无效。')
                require(self.headers.get('Content-Type') == 'application/json', '保存格式无效。')
                length = int(self.headers.get('Content-Length', '0'))
                require(0 < length <= 2 * 1024 * 1024, '项目文件过大或为空。')
                data = json.loads(self.rfile.read(length))
                return self.send(200, dict(project=studio.save(data)))
            if self.path == '/api/health':
                return self.send(200, dict(studio=INSTANCE_ID))
            if self.path == '/api/project':
                return self.send(200, studio.response())
            if self.path.startswith('/api/icon/'):
                uid = int(self.path.removeprefix('/api/icon/'))
                require(uid in studio.icons, '图标不存在。')
                raw = studio.icons[uid].read_bytes()
                return self.send(200, rgba_png(raw), 'image/png')
            files = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8'), '/icon-lettering.otf': ('icon-lettering.otf', 'font/otf')}
            if self.path not in files:
                return self.send(404, dict(error='页面不存在。'))
            name, mime = files[self.path]
            return self.send(200, (ROOT / 'web' / name).read_bytes(), mime)

        def run_request(self):
            try:
                self.dispatch()
            except (ProjectError, ValueError, TypeError, KeyError) as error:
                self.send(getattr(error, 'status', 400), dict(error=str(error)))
            except OSError:
                self.send(500, dict(error='本地文件读写失败，现有项目已保留。'))

        do_GET = run_request
        do_POST = run_request

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def launch():
    address = 'http://127.0.0.1:8877/'
    opener = build_opener(ProxyHandler({}))

    def ready():
        try:
            with opener.open(address + 'api/health', timeout=0.25) as response:
                return json.loads(response.read(1024)) == {'studio': INSTANCE_ID}
        except (OSError, ValueError):
            return False

    if not ready():
        data = ROOT / '.local-data'
        data.mkdir(exist_ok=True)
        with (data / 'studio.log').open('ab') as log:
            process = subprocess.Popen(
                [sys.executable, '-B', str(ROOT / 'app.py'), '--no-browser'],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                start_new_session=True,
            )
        for _ in range(50):
            if ready():
                break
            if process.poll() is not None:
                # Another launcher may have started Studio at the same time.
                if ready():
                    break
                raise SystemExit(f'Studio 启动失败，请查看 {log.name}')
            time.sleep(0.1)
        else:
            raise SystemExit(f'Studio 未能及时启动，请查看 {log.name}')
    if '--no-browser' not in sys.argv:
        webbrowser.open(address)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument('--data', type=Path)
    parser.add_argument('--port', type=int, default=8877)
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    try:
        library = args.library.resolve()
        default_data = ROOT / '.local-data' if library == DEFAULT_LIBRARY else library.parent / '.studio-lite'
        server = make_server(Studio(library, args.data or default_data), args.port)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, '启动失败：' + str(error) + '\n')
    address = f'http://127.0.0.1:{server.server_port}/'
    print('GRSlot Studio Lite  ' + address, flush=True)
    if not args.no_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    if '--launch' in sys.argv:
        launch()
    else:
        main()
