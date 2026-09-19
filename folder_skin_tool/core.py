"""Local, reversible folder icons. All changes are journalled before touching a folder."""
from __future__ import annotations
import base64
import contextlib
import ctypes
from ctypes import wintypes
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import uuid
import msvcrt

from PIL import Image, ImageDraw, ImageColor, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parent
SIZES = [(n, n) for n in (16, 32, 48, 64, 128, 256)]
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
kernel.GetFileAttributesW.restype = wintypes.DWORD
kernel.SetFileAttributesW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
kernel.SetFileAttributesW.restype = wintypes.BOOL
shell = ctypes.WinDLL('shell32')
shell.SHChangeNotify.argtypes = [wintypes.LONG, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p]

def attrs(path):
    value = kernel.GetFileAttributesW(str(path))
    if value == 0xFFFFFFFF:
        raise ctypes.WinError(ctypes.get_last_error())
    return value

def setattrs(path, value):
    if not kernel.SetFileAttributesW(str(path), value or 0x80):
        raise ctypes.WinError(ctypes.get_last_error())

def refresh(path):
    shell.SHChangeNotify(0x2000, 0x0005, ctypes.cast(ctypes.c_wchar_p(str(path)), ctypes.c_void_p), None)
    shell.SHChangeNotify(0x08000000, 0, None, None)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read_optional(path):
    if path.exists():
        if attrs(path) & 0x400 or not path.is_file():
            raise ValueError('设置文件是链接或不是普通文件，已停止操作。')
        return path.read_bytes()
    return None

def write_bytes(path, data):
    # OPEN_EXISTING allows updating hidden/system files without CREATE_ALWAYS.
    with open(path, 'r+b' if path.exists() else 'xb') as stream:
        stream.write(data)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())

def decode_ini(data):
    if data is None:
        return ''
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        return data.decode('utf-16')
    try:
        return data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return data.decode('mbcs')

def customized_ini(original, icon_name):
    text = decode_ini(original)
    lines = text.splitlines()
    output, found, inside = [], False, False
    for line in lines:
        section = re.match(r'^\s*\[([^]]+)\]\s*$', line)
        if section:
            inside = section[1].lower() == '.shellclassinfo'
            output.append(line)
            if inside and not found:
                output.append('IconResource=' + icon_name + ',0')
                found = True
        elif inside and re.match(r'^\s*(IconResource|IconFile|IconIndex)\s*=', line, re.I):
            continue
        else:
            output.append(line)
    if not found:
        output += ['[.ShellClassInfo]', 'IconResource=' + icon_name + ',0']
    return ('\r\n'.join(output) + '\r\n').encode('utf-16')

def load_png(path):
    with Image.open(path) as src:
        if src.format != 'PNG':
            raise ValueError('请选择 PNG 图片。')
        sprite = src.convert('RGBA')
    box = sprite.getchannel('A').getbbox()
    if box is None:
        raise ValueError('图片完全透明，请选择可见的 PNG 素材。')
    return sprite.crop(box)

def layout_image(skin, scale, offset, x_offset=0, bounds=None):
    left, top, right, bottom = bounds or (32, 213, 480, 473)
    ratio = min((right-left) / skin.width, (bottom-top) / skin.height) * float(scale)
    skin = skin.resize((max(1, round(skin.width * ratio)), max(1, round(skin.height * ratio))), Image.Resampling.LANCZOS)
    return skin, (left + right - skin.width) // 2 + int(x_offset), bottom - skin.height + int(offset)

def skin_layout(path, scale, offset, x_offset=0, bounds=None):
    return layout_image(load_png(path), scale, offset, x_offset, bounds)

def compose_single(path, scale=1.0, x_offset=0, y_offset=0):
    if not path:
        raise ValueError('请为当前制作模式选择一张 PNG 图片。')
    sprite = load_png(path)
    ratio = min(480 / sprite.width, 480 / sprite.height) * float(scale)
    sprite = sprite.resize((max(1, round(sprite.width * ratio)), max(1, round(sprite.height * ratio))), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (512, 512))
    canvas.alpha_composite(sprite, ((512-sprite.width)//2+int(x_offset), (512-sprite.height)//2+int(y_offset)))
    return canvas

def compose(character, color='#9973df', scale=1.0, offset=0,
            folder_skin=None, skin_scale=1.0, skin_offset=0,
            depth=True, opening_left=.35, opening_right=.25, shadow=.35,
            character_x=0, skin_x=0, folder_bounds=None):
    """Draw the back, character and front in that order, at double resolution."""
    canvas = Image.new('RGBA', (512, 512))
    draw = ImageDraw.Draw(canvas)
    rgb = ImageColor.getrgb(color)
    dark = tuple(int(c * .72) for c in rgb)
    light = tuple(min(255, int(c * .8 + 51)) for c in rgb)
    if not folder_skin:
        draw.rounded_rectangle((42, 213, 238, 305), 23, fill=dark)
        draw.rounded_rectangle((42, 246, 470, 458), 27, fill=dark)
    sprite = load_png(character)
    ratio = min(340 / sprite.width, 310 / sprite.height) * float(scale)
    sprite = sprite.resize((max(1, round(sprite.width * ratio)), max(1, round(sprite.height * ratio))), Image.Resampling.LANCZOS)
    character_layer = Image.new('RGBA', canvas.size)
    character_layer.alpha_composite(sprite, ((512 - sprite.width) // 2 + int(character_x), 345 - sprite.height + int(offset)))
    front = Image.new('RGBA', canvas.size)
    if folder_skin:
        skin, x, y = skin_layout(folder_skin, skin_scale, skin_offset, skin_x, folder_bounds)
        if depth:
            mask = Image.new('L', skin.size)
            ImageDraw.Draw(mask).polygon([(0, round(skin.height * opening_left)),
                                          (skin.width, round(skin.height * opening_right)),
                                          (skin.width, skin.height), (0, skin.height)], fill=255)
            back = skin.copy()
            back.putalpha(ImageChops.multiply(skin.getchannel('A'), ImageChops.invert(mask)))
            canvas.alpha_composite(back, (x, y))
            skin.putalpha(ImageChops.multiply(skin.getchannel('A'), mask))
        front.alpha_composite(skin, (x, y))
    else:
        draw = ImageDraw.Draw(front)
        draw.rounded_rectangle((32, 303, 480, 473), 28, fill=rgb)
        draw.rounded_rectangle((48, 316, 464, 328), 6, fill=light)
        draw.line((62, 452, 448, 452), fill=dark, width=3)
        if folder_bounds is not None or skin_scale != 1 or skin_offset or skin_x:
            # Apply the same transform to both halves of the built-in folder.
            for layer in (canvas, front):
                fitted, x, y = layout_image(layer.crop((32, 213, 481, 474)),
                                           skin_scale, skin_offset, skin_x, folder_bounds)
                layer.paste((0, 0, 0, 0), (0, 0, 512, 512))
                layer.alpha_composite(fitted, (x, y))
    if depth and shadow > 0:
        # The front lip casts a soft contact shadow only onto visible character pixels.
        front_alpha = front.getchannel('A')
        contact = front_alpha.filter(ImageFilter.GaussianBlur(9))
        contact = ImageChops.multiply(contact, ImageChops.invert(front_alpha))
        contact = ImageChops.multiply(contact, character_layer.getchannel('A'))
        contact = contact.point(lambda value: round(value * min(1, max(0, shadow))))
        shade = Image.new('RGBA', canvas.size, (25, 18, 35, 0))
        shade.putalpha(contact)
        character_layer.alpha_composite(shade)
    canvas.alpha_composite(character_layer)
    canvas.alpha_composite(front)
    return canvas

def fit_icon_content(image, margin=4, zoom=1.0):
    """Fit the visible silhouette; optional zoom deliberately crops at canvas edges."""
    image = image.convert('RGBA')
    alpha = image.getchannel('A')
    box = alpha.point(lambda value: 255 if value > 16 else 0).getbbox() or alpha.getbbox()
    if box is None:
        return image.copy(), (1, 1, 0, 0)
    crop = image.crop(box)
    ratio = min((image.width - 2 * margin) / crop.width,
                (image.height - 2 * margin) / crop.height) * float(zoom)
    size = (max(1, round(crop.width * ratio)), max(1, round(crop.height * ratio)))
    x, y = (image.width - size[0]) // 2, (image.height - size[1]) // 2
    fitted = Image.new('RGBA', image.size)
    fitted.alpha_composite(crop.resize(size, Image.Resampling.LANCZOS), (x, y))
    sx, sy = size[0] / crop.width, size[1] / crop.height
    return fitted, (sx, sy, x - box[0] * sx, y - box[1] * sy)

def export_icon(image, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination.with_suffix('.png'))
    image.save(destination.with_suffix('.ico'), format='ICO', sizes=SIZES)
    return destination.with_suffix('.ico')

def icon_bytes(image):
    stream = BytesIO()
    image.save(stream, format='ICO', sizes=SIZES)
    return stream.getvalue()

def png_to_icon_bytes(source):
    """Convert the complete PNG, preserving its aspect ratio and transparency."""
    with Image.open(source) as image:
        if image.format != 'PNG':
            raise ValueError('请选择有效的 PNG 图片。')
        image = image.convert('RGBA')
    ratio = min(512 / image.width, 512 / image.height)
    size = (max(1, round(image.width * ratio)), max(1, round(image.height * ratio)))
    resized = image.resize(size, Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (512, 512))
    canvas.alpha_composite(resized, ((512-size[0])//2, (512-size[1])//2))
    return icon_bytes(canvas)

def create_sample(path):
    image = Image.new('RGBA', (400, 400))
    d = ImageDraw.Draw(image)
    d.ellipse((65, 24, 335, 304), fill='#ede5ff', outline='#674ea7', width=7)
    d.polygon([(69, 166), (67, 355), (126, 321), (178, 361), (227, 322), (282, 354), (332, 315), (332, 167)], fill='#ede5ff')
    d.ellipse((120, 135, 152, 188), fill='#41335e')
    d.ellipse((244, 135, 276, 188), fill='#41335e')
    d.ellipse((100, 197, 151, 220), fill='#f7b6d2')
    d.ellipse((248, 197, 299, 220), fill='#f7b6d2')
    d.arc((164, 181, 230, 231), 0, 180, fill='#41335e', width=6)
    image.save(path)

class SkinStore:
    def __init__(self, data_dir=ROOT / 'data'):
        self.directory = Path(data_dir)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.registry = self.directory / 'skin_registry.json'

    @contextlib.contextmanager
    def locked(self):
        with open(self.directory / 'registry.lock', 'a+b') as lock:
            lock.seek(0)
            if not lock.read(1):
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError('另一个工具窗口正在操作，请稍后重试。')
            try:
                yield
            finally:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)

    def load(self):
        if not self.registry.exists():
            return {'version': 1, 'folders': {}}
        data = json.loads(self.registry.read_text(encoding='utf-8'))
        if data.get('version') != 1 or not isinstance(data.get('folders'), dict):
            raise ValueError('记录文件格式不正确；为保护备份，已停止操作。')
        return data

    def save(self, data):
        temp = self.registry.with_suffix('.tmp')
        with open(temp, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.registry)

    def target(self, folder):
        path = Path(os.path.abspath(folder))
        if not path.is_dir() or path == Path(path.anchor) or str(path).startswith('\\\\'):
            raise ValueError('请选择本地磁盘中的普通文件夹，不能选择磁盘根目录。')
        for part in [path, *path.parents]:
            if attrs(part) & 0x400:
                raise ValueError('暂不支持链接、联接点或云端占位目录。')
        return path

    def apply(self, folder, ico):
        path = self.target(folder)
        icon_data = ico if isinstance(ico, bytes) else Path(ico).read_bytes()
        if not icon_data.startswith(b'\x00\x00\x01\x00'):
            raise ValueError('图标文件格式不正确。')
        key = str(path).casefold()
        with self.locked():
            data = self.load()
            if key in data['folders']:
                self._restore(data, key)
            ini = path / 'desktop.ini'
            original = read_optional(ini)
            icon_name = '.folder_skin_' + uuid.uuid4().hex + '.ico'
            modified = customized_ini(original, icon_name)
            entry = {
                'path': str(path), 'identity': path.stat().st_ino,
                'folder_attributes': attrs(path),
                'original_ini': base64.b64encode(original).decode() if original is not None else None,
                'ini_attributes': attrs(ini) if original is not None else None,
                'modified_ini': base64.b64encode(modified).decode(),
                'icon_name': icon_name, 'icon_hash': digest(icon_data), 'state': 'pending',
            }
            data['folders'][key] = entry
            self.save(data)
            try:
                with open(path / icon_name, 'xb') as stream:
                    stream.write(icon_data)
                setattrs(path / icon_name, 2 | 4)
                if original is not None:
                    setattrs(ini, attrs(ini) & ~1)
                write_bytes(ini, modified)
                setattrs(ini, (entry['ini_attributes'] or 0) | 2 | 4)
                setattrs(path, attrs(path) | 1)
                entry['state'] = 'active'
                self.save(data)
            except Exception:
                # Keep the journal so Restore can recover a partially completed operation.
                raise
            finally:
                refresh(path)

    def restore(self, folder):
        key = str(Path(os.path.abspath(folder))).casefold()
        with self.locked():
            data = self.load()
            if key not in data['folders']:
                raise ValueError('此文件夹没有本工具的换肤记录，没有修改任何内容。')
            self._restore(data, key)

    def _restore(self, data, key):
        entry = data['folders'][key]
        path = self.target(entry['path'])
        if path.stat().st_ino != entry['identity']:
            raise ValueError('目标文件夹已被替换，保留记录以避免误改。')
        ini = path / 'desktop.ini'
        original = base64.b64decode(entry['original_ini']) if entry['original_ini'] is not None else None
        modified = base64.b64decode(entry['modified_ini'])
        current = read_optional(ini)
        if current not in (original, modified):
            raise ValueError('desktop.ini 在换肤后被其他程序更改，已保留所有文件和备份，未覆盖这些更改。')
        icon = path / entry['icon_name']
        icon_data = read_optional(icon)
        if icon_data is not None and digest(icon_data) != entry['icon_hash']:
            raise ValueError('本工具的图标文件已被外部更改，已停止恢复并保留备份。')
        if current is not None:
            setattrs(ini, attrs(ini) & ~1)
        if original is None:
            if ini.exists():
                ini.unlink()
        else:
            write_bytes(ini, original)
            setattrs(ini, entry['ini_attributes'])
        # Only undo the directory read-only bit we changed.
        setattrs(path, (attrs(path) & ~1) | (entry['folder_attributes'] & 1))
        if icon.exists():
            setattrs(icon, attrs(icon) & ~1)
            icon.unlink()
        del data['folders'][key]
        self.save(data)
        refresh(path)

    def restore_all(self):
        failures, count = [], 0
        with self.locked():
            data = self.load()
            for key in list(data['folders']):
                try:
                    self._restore(data, key)
                    count += 1
                except Exception as exc:
                    failures.append(data['folders'][key]['path'] + ': ' + str(exc))
        return count, failures
