import copy
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from core import icon_bytes
from system_skin import SystemSkin


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


if __name__ == '__main__':
    unittest.main()
