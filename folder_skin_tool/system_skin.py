"""Reversible machine-wide Shell icon override. CLI operations require elevation."""
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import winreg
from core import SkinStore, refresh

KEY = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Icons'
DIRECTORY = Path(os.environ['ProgramData']) / 'FolderSkinTool'


class Registry:
    def read(self, name):
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
                value, kind = winreg.QueryValueEx(key, name)
        except FileNotFoundError:
            return None
        return {'type': kind, 'data': base64.b64encode(value).decode() if isinstance(value, bytes) else value,
                'binary': isinstance(value, bytes)}

    def write(self, name, record):
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE, KEY, 0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
            if record is None:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            else:
                value = base64.b64decode(record['data']) if record['binary'] else record['data']
                winreg.SetValueEx(key, name, 0, record['type'], value)
            winreg.FlushKey(key)


class SystemSkin:
    def __init__(self, directory=DIRECTORY, registry=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_path = self.directory / 'system_backup.json'
        self.registry = registry or Registry()

    def load(self):
        if not self.state_path.exists():
            return None
        state = json.loads(self.state_path.read_text(encoding='utf-8'))
        if state.get('version') != 1 or set(state['original']) != {'3', '4'}:
            raise ValueError('系统图标备份格式不正确，已停止操作。')
        return state

    def save(self, state):
        temp = self.state_path.with_suffix('.tmp')
        with open(temp, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.state_path)

    def check(self, state):
        for name in ('3', '4'):
            current = self.registry.read(name)
            if current != state['original'][name] and current not in state['managed']:
                raise ValueError('系统文件夹图标已被其他软件修改；为避免覆盖，保留备份并停止操作。')

    def apply(self, icon_data):
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(icon_data)) as image:
            if image.format != 'ICO':
                raise ValueError('需要有效的 ICO 图标。')
            image.load()
        with SkinStore(self.directory).locked():
            state = self.load()
            if state:
                self.check(state)
                if state['status'] != 'active':
                    raise ValueError('上次系统图标操作未完成，请先点击恢复系统默认图标。')
            else:
                state = {'version': 1, 'original': {n: self.registry.read(n) for n in ('3', '4')},
                         'managed': [], 'icons': []}
            icon = self.directory / ('system_' + uuid.uuid4().hex + '.ico')
            with open(icon, 'xb') as stream:
                stream.write(icon_data)
                stream.flush()
                os.fsync(stream.fileno())
            record = {'type': winreg.REG_SZ, 'data': str(icon) + ',0', 'binary': False}
            state['managed'].append(record)
            state['icons'].append(icon.name)
            state['status'] = 'pending'
            self.save(state)
            for name in ('3', '4'):
                self.registry.write(name, record)
            state['status'] = 'active'
            self.save(state)

    def restore(self):
        with SkinStore(self.directory).locked():
            state = self.load()
            if state is None:
                raise ValueError('没有本工具的系统图标备份，未修改任何设置。')
            self.check(state)
            state['status'] = 'restoring'
            self.save(state)
            for name in ('3', '4'):
                self.registry.write(name, state['original'][name])
            # Remove only our generated ICOs after registry restoration succeeds.
            import re
            for name in state['icons']:
                if re.fullmatch(r'system_[0-9a-f]{32}\.ico', name):
                    (self.directory / name).unlink(missing_ok=True)
            self.state_path.unlink()


def run_elevated(operation, request_dir):
    """Wait in a worker thread; the Windows UAC prompt is the only elevation UI."""
    class ExecuteInfo(ctypes.Structure):
        _fields_ = [('cbSize', wintypes.DWORD), ('fMask', wintypes.ULONG), ('hwnd', wintypes.HWND),
                    ('lpVerb', wintypes.LPCWSTR), ('lpFile', wintypes.LPCWSTR),
                    ('lpParameters', wintypes.LPCWSTR), ('lpDirectory', wintypes.LPCWSTR),
                    ('nShow', ctypes.c_int), ('hInstApp', wintypes.HINSTANCE), ('lpIDList', ctypes.c_void_p),
                    ('lpClass', wintypes.LPCWSTR), ('hkeyClass', wintypes.HKEY), ('dwHotKey', wintypes.DWORD),
                    ('hIcon', wintypes.HANDLE), ('hProcess', wintypes.HANDLE)]
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ExecuteInfo)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    info = ExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40 | 0x100
    info.lpVerb = 'runas'
    info.lpFile = sys.executable
    info.lpParameters = subprocess.list2cmdline([str(Path(__file__).resolve()), operation, str(request_dir)])
    info.lpDirectory = str(Path(__file__).resolve().parent)
    info.nShow = 0
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.get_last_error()
        if error == 1223:
            raise RuntimeError('已取消管理员授权，未执行系统图标操作。')
        raise ctypes.WinError(error)
    try:
        if kernel.WaitForSingleObject(info.hProcess, 0xFFFFFFFF) != 0:
            raise RuntimeError('等待系统图标操作失败，请检查备份后重试。')
    finally:
        kernel.CloseHandle(info.hProcess)
    result_path = Path(request_dir) / 'result.json'
    if not result_path.exists():
        raise RuntimeError('系统操作未返回结果；若曾开始写入，可用恢复按钮恢复。')
    result = json.loads(result_path.read_text(encoding='utf-8'))
    if not result['ok']:
        raise RuntimeError(result['error'])


def main():
    operation, request = sys.argv[1:]
    request = Path(request)
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise PermissionError('此操作需要管理员权限。')
        store = SystemSkin()
        if operation == 'apply':
            store.apply((request / 'input.ico').read_bytes())
        elif operation == 'restore':
            store.restore()
        else:
            raise ValueError('未知操作。')
        refresh(DIRECTORY)
        result = {'ok': True}
    except Exception as exc:
        result = {'ok': False, 'error': str(exc)}
    (request / 'result.json').write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    main()
