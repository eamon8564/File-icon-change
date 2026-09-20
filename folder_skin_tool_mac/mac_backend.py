"""Finder custom icons through AppKit; no system resource or SIP modifications."""
import base64
import contextlib
import errno
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import sys
from PIL import Image
from imaging import png_bytes

DATA = Path.home() / 'Library' / 'Application Support' / 'FolderSkinToolMac'


def appkit():
    if sys.platform != 'darwin':
        raise RuntimeError('Finder 换肤需要在 macOS 上运行。图片制作和格式转换可独立使用。')
    try:
        from AppKit import NSWorkspace, NSImage
        from Foundation import NSData
    except ImportError as exc:
        raise RuntimeError('缺少 macOS 依赖，请先运行 Setup.command。') from exc
    return NSWorkspace, NSImage, NSData


def attribute(path, name):
    try:
        return os.getxattr(path, name, follow_symlinks=False)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, getattr(errno, 'ENOATTR', 93), getattr(errno, 'ENODATA', 61)):
            return b''
        raise


class Finder:
    def custom(self, path):
        info = attribute(path, 'com.apple.FinderInfo')
        return len(info) >= 10 and bool(int.from_bytes(info[8:10], 'big') & 0x400)

    def fingerprint(self, path):
        icon_file = path / 'Icon\r'
        if icon_file.is_symlink():
            raise ValueError('文件夹图标资源是符号链接，停止操作。')
        parts = [b'custom' if self.custom(path) else b'default']
        if icon_file.exists():
            if not icon_file.is_file():
                raise ValueError('Icon 资源不是普通文件。')
            parts += [icon_file.read_bytes(), attribute(icon_file, 'com.apple.ResourceFork')]
        return hashlib.sha256(b'\x00'.join(parts)).hexdigest()

    def snapshot(self, path):
        if not self.custom(path):
            if (path / 'Icon\r').exists():
                raise ValueError('文件夹已有未知的 Icon 资源文件，停止操作以免覆盖。')
            return None
        Workspace, _, _ = appkit()
        data = Workspace.sharedWorkspace().iconForFile_(str(path)).TIFFRepresentation()
        if data is None:
            raise RuntimeError('无法备份已有图标，未开始换肤。')
        return bytes(data)

    def set(self, path, data):
        Workspace, NSImage, NSData = appkit()
        image = None
        if data is not None:
            image = NSImage.alloc().initWithData_(NSData.dataWithBytes_length_(data, len(data)))
            if image is None:
                raise ValueError('macOS 无法读取图标图片。')
        if not Workspace.sharedWorkspace().setIcon_forFile_options_(image, str(path), 0):
            raise PermissionError('Finder 无法设置图标。请检查文件夹写权限及 macOS「文件与文件夹」访问权限。')
        Workspace.sharedWorkspace().noteFileSystemChanged_(str(path))


def default_folder_bounds():
    _, NSImage, _ = appkit()
    native = NSImage.imageNamed_('NSFolder')
    if native is None or native.TIFFRepresentation() is None:
        raise RuntimeError('无法读取 Mac 默认文件夹图标。')
    with Image.open(BytesIO(bytes(native.TIFFRepresentation()))) as image:
        image = image.convert('RGBA')
        box = image.getchannel('A').point(lambda a: 255 if a > 16 else 0).getbbox()
        if box is None:
            raise RuntimeError('默认文件夹图标为空。')
        return (round(box[0]*512/image.width), round(box[1]*512/image.height),
                round(box[2]*512/image.width), round(box[3]*512/image.height))


class SkinStore:
    def __init__(self, directory=DATA, backend=None):
        # Delay filesystem writes until an operation is requested.
        self.directory = Path(directory)
        self.registry = self.directory / 'skin_registry.json'
        self.backend = backend or Finder()

    @contextlib.contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.directory / 'registry.lock', 'a+b') as lock:
            if sys.platform == 'win32':
                # Enables simulation tests on the development machine.
                import msvcrt
                lock.seek(0)
                if not lock.read(1):
                    lock.write(b'0'); lock.flush()
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                try:
                    yield
                finally:
                    lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    yield
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def load(self):
        if not self.registry.exists():
            return {'version': 1, 'folders': {}}
        data = json.loads(self.registry.read_text(encoding='utf-8'))
        if data.get('version') != 1 or not isinstance(data.get('folders'), dict):
            raise ValueError('备份格式不正确，已停止操作。')
        return data

    def save(self, data):
        temporary = self.registry.with_suffix('.tmp')
        with open(temporary, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, self.registry)

    def target(self, folder):
        path = Path(os.path.abspath(os.path.expanduser(str(folder))))
        if not path.is_dir() or path == Path(path.anchor):
            raise ValueError('请选择普通文件夹，不能选择磁盘根目录。')
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise ValueError('暂不支持符号链接目录。')
        if sys.platform == 'darwin':
            if any(path == p or p in path.parents for p in map(Path, ['/System', '/Library', '/Applications', '/usr', '/bin', '/sbin'])) or path == Path('/Users'):
                raise ValueError('请选择自己的普通文件夹，不修改系统目录或应用。')
            if any(p.suffix.lower() in ('.app', '.bundle', '.framework') for p in (path, *path.parents)):
                raise ValueError('暂不支持应用包内部目录。')
        return path

    @staticmethod
    def identity(path):
        info = path.stat()
        return [info.st_dev, info.st_ino]

    def apply(self, folder, image):
        path = self.target(folder)
        payload = png_bytes(image)
        key = str(path)  # macOS volumes may be case-sensitive.
        with self.locked():
            data = self.load()
            if key in data['folders']:
                self._restore(data, key)
            original = self.backend.snapshot(path)
            before = self.backend.fingerprint(path)
            entry = {'path': key, 'identity': self.identity(path),
                     'original': base64.b64encode(original).decode() if original is not None else None,
                     'before': before, 'expected': None, 'state': 'pending'}
            data['folders'][key] = entry
            self.save(data)
            self.backend.set(path, payload)
            entry['expected'] = self.backend.fingerprint(path)
            entry['state'] = 'active'
            self.save(data)

    def _restore(self, data, key):
        entry = data['folders'][key]
        path = self.target(entry['path'])
        if self.identity(path) != entry['identity']:
            raise ValueError('原路径的文件夹已被替换，停止恢复。')
        current = self.backend.fingerprint(path)
        if entry['state'] == 'pending' and current != entry['before']:
            raise ValueError('上次换肤中断，无法确认当前图标归属。已保留原图标备份，请依据指南手动恢复。')
        if entry['state'] == 'active' and current != entry['expected']:
            raise ValueError('图标已被其他程序修改，保留备份并停止覆盖。')
        if entry['state'] == 'restoring':
            # A successful visual restoration may encode the resource differently.
            if current != entry['expected']:
                raise ValueError('上次恢复中断，保留备份，请检查当前图标后手动处理。')
        original = base64.b64decode(entry['original']) if entry['original'] is not None else None
        entry['state'] = 'restoring'
        self.save(data)
        self.backend.set(path, original)
        del data['folders'][key]
        self.save(data)

    def restore(self, folder):
        key = str(self.target(folder))
        with self.locked():
            data = self.load()
            if key not in data['folders']:
                raise ValueError('没有此文件夹的换肤记录。')
            self._restore(data, key)

    def restore_all(self):
        count, errors = 0, []
        with self.locked():
            data = self.load()
            for key in list(data['folders']):
                try:
                    self._restore(data, key); count += 1
                except Exception as exc:
                    errors.append(key + ': ' + str(exc))
        return count, errors
