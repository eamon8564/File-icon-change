import base64
from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image
from imaging import (compose, compose_single, create_sample, fit_icon_content,
                     icon_bytes, png_to_icon_bytes, icns_bytes, SIZES)
from mac_backend import SkinStore, Finder


class FakeFinder:
    def __init__(self):
        self.icons = {}
    def snapshot(self, path):
        return self.icons.get(str(path))
    def fingerprint(self, path):
        import hashlib
        return hashlib.sha256(self.icons.get(str(path)) or b'default').hexdigest()
    def set(self, path, data):
        self.icons[str(path)] = data


class MacToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.folder = self.root / '文件夹'
        self.folder.mkdir()
        self.file = self.folder / 'keep.txt'
        self.file.write_text('unchanged')
        self.backend = FakeFinder()
        self.store = SkinStore(self.root / 'data', self.backend)
        self.image = Image.new('RGBA', (512, 512), 'purple')
    def tearDown(self):
        self.temp.cleanup()

    def test_apply_restore_default(self):
        self.store.apply(self.folder, self.image)
        self.assertEqual(len(self.store.load()['folders']), 1)
        self.store.restore(self.folder)
        self.assertIsNone(self.backend.snapshot(self.folder))
        self.assertEqual(self.file.read_text(), 'unchanged')

    def test_reapply_preserves_original_custom_icon(self):
        self.backend.set(self.folder, b'original image')
        self.store.apply(self.folder, self.image)
        self.store.apply(self.folder, Image.new('RGBA', (128, 128), 'red'))
        self.store.restore(self.folder)
        self.assertEqual(self.backend.snapshot(self.folder), b'original image')

    def test_external_change_is_not_overwritten(self):
        self.store.apply(self.folder, self.image)
        self.backend.set(self.folder, b'changed by someone else')
        with self.assertRaises(ValueError):
            self.store.restore(self.folder)
        self.assertEqual(self.backend.snapshot(self.folder), b'changed by someone else')

    def test_restore_all_only_tracks_own_folders(self):
        other = self.root / 'other'; other.mkdir()
        self.backend.set(other, b'keep')
        self.store.apply(self.folder, self.image)
        self.assertEqual(self.store.restore_all(), (1, []))
        self.assertEqual(self.backend.snapshot(other), b'keep')

    def test_replaced_directory_is_refused(self):
        self.store.apply(self.folder, self.image)
        self.folder.rename(self.root / 'moved')
        self.folder.mkdir()
        with self.assertRaises(ValueError):
            self.store.restore(self.folder)

    def test_pending_unknown_change_keeps_backup(self):
        self.store.apply(self.folder, self.image)
        data = self.store.load()
        data['folders'][str(self.folder)]['state'] = 'pending'
        self.store.save(data)
        with self.assertRaises(ValueError):
            self.store.restore(self.folder)
        self.assertTrue(self.store.load()['folders'])

    def test_bad_registry_stops_apply(self):
        self.store.directory.mkdir()
        self.store.registry.write_text('invalid')
        with self.assertRaises(ValueError):
            self.store.apply(self.folder, self.image)
        self.assertIsNone(self.backend.snapshot(self.folder))

    def test_ico_all_sizes(self):
        with Image.open(BytesIO(icon_bytes(self.image))) as image:
            self.assertEqual(image.ico.sizes(), set(SIZES))

    def test_icns_roundtrip(self):
        with Image.open(BytesIO(icns_bytes(self.image))) as image:
            self.assertEqual(image.format, 'ICNS')
            self.assertEqual(image.size, (1024, 1024))
            self.assertEqual(image.convert('RGBA').getpixel((512,512)), (128,0,128,255))

    def test_direct_png_keeps_aspect_ratio(self):
        path = self.root / 'wide.png'
        Image.new('RGBA', (400, 200), 'blue').save(path)
        original = path.read_bytes()
        with Image.open(BytesIO(png_to_icon_bytes(path))) as icon:
            alpha = icon.ico.getimage((256,256)).getchannel('A')
            self.assertEqual(alpha.point(lambda a: 255 if a > 128 else 0).getbbox(), (0,64,256,192))
        self.assertEqual(path.read_bytes(), original)

    def test_composition_and_single_png(self):
        path = self.root / 'character.png'; create_sample(path)
        single = compose_single(path)
        combo = compose(path, character_x=25, skin_x=-20)
        self.assertNotEqual(single.tobytes(), combo.tobytes())
        self.assertEqual(fit_icon_content(combo)[0].size, (512,512))
        self.assertEqual(combo.getpixel((0,0))[3], 0)

    @unittest.skipUnless(sys.platform == 'darwin' and os.environ.get('FOLDER_SKIN_MAC_TEST') == '1', 'Requires explicit macOS integration test opt-in')
    def test_native_finder_on_temporary_folder(self):
        store = SkinStore(self.root/'native_data')
        store.apply(self.folder, self.image)
        self.assertTrue(Finder().custom(self.folder))
        store.restore(self.folder)
        self.assertFalse(Finder().custom(self.folder))
        self.assertEqual(self.file.read_text(), 'unchanged')


if __name__ == '__main__':
    unittest.main()
