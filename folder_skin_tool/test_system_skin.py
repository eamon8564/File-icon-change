import copy
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from core import icon_bytes
from system_skin import SystemSkin
from system_skin import prepare_request, write_result, validate_icon
import json
from unittest.mock import patch


class FakeRegistry:
    def __init__(self):
        self.values = {'3': {'type': 2, 'data': '%SystemRoot%/old.ico,0', 'binary': False}, '4': None}
        self.fail_next = None

    def read(self, name):
        return copy.deepcopy(self.values[name])

    def write(self, name, record):
        if self.fail_next == name:
            self.fail_next = None
            raise OSError('simulated interruption')
        self.values[name] = copy.deepcopy(record)


class SystemSkinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.registry = FakeRegistry()
        self.original = copy.deepcopy(self.registry.values)
        self.store = SystemSkin(self.temp.name, self.registry)
        self.icon = icon_bytes(Image.new('RGBA', (256, 256), 'purple'))

    def tearDown(self):
        self.temp.cleanup()

    def test_repeated_apply_restores_first_original(self):
        self.store.apply(self.icon)
        first = self.registry.read('3')
        self.store.apply(self.icon)
        self.assertNotEqual(first, self.registry.read('3'))
        self.assertEqual(self.store.load()['original'], self.original)
        self.store.restore()
        self.assertEqual(self.registry.values, self.original)
        self.assertFalse(self.store.state_path.exists())
        self.assertFalse(list(Path(self.temp.name).glob('*.ico')))

    def test_partial_apply_can_restore(self):
        self.registry.fail_next = '4'
        with self.assertRaises(OSError):
            self.store.apply(self.icon)
        self.assertEqual(self.store.load()['status'], 'pending')
        with self.assertRaises(ValueError):
            self.store.apply(self.icon)
        self.store.restore()
        self.assertEqual(self.registry.values, self.original)

    def test_partial_restore_can_retry(self):
        self.store.apply(self.icon)
        self.registry.fail_next = '4'
        with self.assertRaises(OSError):
            self.store.restore()
        self.assertTrue(self.store.state_path.exists())
        self.store.restore()
        self.assertEqual(self.registry.values, self.original)

    def test_external_change_is_preserved(self):
        self.store.apply(self.icon)
        self.registry.values['4'] = {'type': 1, 'data': 'third-party.ico', 'binary': False}
        current = copy.deepcopy(self.registry.values)
        with self.assertRaises(ValueError):
            self.store.restore()
        with self.assertRaises(ValueError):
            self.store.apply(self.icon)
        self.assertEqual(self.registry.values, current)
        self.assertTrue(self.store.state_path.exists())

    def test_invalid_icon_and_missing_backup_do_not_change_registry(self):
        with self.assertRaises(Exception):
            self.store.apply(b'not an icon')
        with self.assertRaises(ValueError):
            self.store.restore()
        self.assertEqual(self.registry.values, self.original)

    def test_unrelated_file_is_preserved(self):
        file = Path(self.temp.name) / 'keep.txt'
        file.write_text('keep')
        self.store.apply(self.icon)
        self.store.restore()
        self.assertEqual(file.read_text(), 'keep')

    def test_result_updates_existing_file_without_replacement(self):
        prepare_request(self.temp.name, self.icon)
        result = Path(self.temp.name) / 'result.json'
        identity = result.stat().st_ino
        write_result(self.temp.name, {'ok': False, 'error': 'long message' * 30})
        write_result(self.temp.name, {'ok': True})
        self.assertEqual(result.stat().st_ino, identity)
        self.assertEqual(json.loads(result.read_text(encoding='utf-8')), {'ok': True})
        self.assertEqual((Path(self.temp.name) / 'input.ico').read_bytes(), self.icon)

    def test_missing_result_channel_stops_before_registry_changes(self):
        import system_skin
        with patch('sys.argv', ['system_skin.py', 'restore', self.temp.name]), patch.object(system_skin, 'SystemSkin') as store:
            with self.assertRaises(FileNotFoundError):
                system_skin.main()
            store.assert_not_called()

    def test_png_renamed_as_icon_is_rejected(self):
        from io import BytesIO
        stream = BytesIO()
        Image.new('RGBA', (32, 32), 'red').save(stream, format='PNG')
        with self.assertRaises(ValueError):
            validate_icon(stream.getvalue())


if __name__ == '__main__':
    unittest.main()
