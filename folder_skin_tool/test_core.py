import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import core


class SkinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.folder = self.root / '中文 folder'
        self.folder.mkdir()
        self.user_file = self.folder / 'important.txt'
        self.user_file.write_bytes(b'user content')
        self.sample = self.root / 'sample.png'
        core.create_sample(self.sample)
        self.icon = core.export_icon(core.compose(self.sample), self.root / 'preview')
        self.store = core.SkinStore(self.root / 'data')
        self.before = core.attrs(self.folder)

    def tearDown(self):
        for path in self.root.rglob('*'):
            core.setattrs(path, core.attrs(path) & ~7)
        self.temp.cleanup()

    def test_icon_sizes_and_alpha(self):
        with Image.open(self.icon) as image:
            self.assertEqual(image.ico.sizes(), set(core.SIZES))
        with Image.open(self.icon.with_suffix('.png')) as image:
            self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_depth_places_character_between_folder_parts(self):
        character = self.root / 'red.png'
        skin = self.root / 'blue.png'
        Image.new('RGBA', (310, 310), 'red').save(character)
        Image.new('RGBA', (448, 260), 'blue').save(skin)
        kwargs = dict(folder_skin=skin, opening_left=.4, opening_right=.4, shadow=0)
        layered = core.compose(character, **kwargs)
        flat = core.compose(character, depth=False, **kwargs)
        self.assertEqual(layered.getpixel((256, 260)), (255, 0, 0, 255))
        self.assertEqual(flat.getpixel((256, 260)), (0, 0, 255, 255))
        self.assertEqual(layered.getpixel((256, 330)), (0, 0, 255, 255))
        shaded = core.compose(character, **{**kwargs, 'shadow': 1})
        self.assertLess(shaded.getpixel((256, 312))[0], layered.getpixel((256, 312))[0])
        self.assertEqual(shaded.getchannel('A').tobytes(), layered.getchannel('A').tobytes())
        sloped = core.compose(character, **{**kwargs, 'opening_left': .2, 'opening_right': .8})
        self.assertEqual(sloped.getpixel((130, 320)), (0, 0, 255, 255))
        self.assertEqual(sloped.getpixel((380, 320)), (255, 0, 0, 255))

    def test_horizontal_movement_and_folder_fit(self):
        skin = self.root / 'skin.png'
        Image.new('RGBA', (400, 200), 'blue').save(skin)
        fitted, x, y = core.skin_layout(skin, 1, 0, 0, (32, 64, 480, 416))
        self.assertEqual((fitted.width, fitted.height, x, y), (448, 224, 32, 192))
        moved, mx, my = core.skin_layout(skin, 1, 12, 37, (32, 64, 480, 416))
        self.assertEqual((mx-x, my-y), (37, 12))
        ordinary = core.compose(self.sample, shadow=0)
        shifted = core.compose(self.sample, shadow=0, character_x=40)
        self.assertEqual(ordinary.crop((0, 0, 472, 200)).tobytes(), shifted.crop((40, 0, 512, 200)).tobytes())
        together = core.compose(self.sample, shadow=0, character_x=20, skin_x=20, folder_skin=skin)
        normal = core.compose(self.sample, shadow=0, folder_skin=skin)
        self.assertEqual(normal.crop((0, 0, 492, 512)).tobytes(), together.crop((20, 0, 512, 512)).tobytes())

    def test_output_fills_slot_without_clipping(self):
        image = Image.new('RGBA', (512, 512))
        image.paste((80, 90, 100, 255), (117, 98, 421, 410))
        fitted, (sx, sy, tx, ty) = core.fit_icon_content(image, margin=12)
        box = fitted.getchannel('A').getbbox()
        self.assertEqual(box[3] - box[1], 488)
        self.assertGreaterEqual(min(box[0], box[1], 512-box[2], 512-box[3]), 12)
        self.assertAlmostEqual(117*sx+tx, box[0])
        self.assertAlmostEqual(98*sy+ty, box[1])
        icon = core.export_icon(fitted, self.root / 'fitted')
        with Image.open(icon) as result:
            for size in core.SIZES:
                frame = result.ico.getimage(size)
                bounds = frame.getchannel('A').point(lambda a: 255 if a > 16 else 0).getbbox()
                self.assertGreaterEqual(bounds[3]-bounds[1], round(size[1]*.90))

    def test_faint_outliers_do_not_shrink_subject(self):
        image = Image.new('RGBA', (512, 512))
        image.paste((90, 100, 110, 255), (150, 100, 350, 400))
        image.putpixel((0, 0), (50, 50, 50, 1))
        fitted, _ = core.fit_icon_content(image)
        self.assertEqual(fitted.getchannel('A').getbbox(), (88, 4, 424, 508))
        zoomed, _ = core.fit_icon_content(image, zoom=1.2)
        box = zoomed.getchannel('A').getbbox()
        self.assertEqual((box[1], box[3]), (0, 512))
        self.assertGreater(box[2]-box[0], 336)

    def test_apply_restore_and_reapply(self):
        self.store.apply(self.folder, self.icon)
        self.assertTrue(core.attrs(self.folder) & 1)
        self.assertEqual(core.attrs(self.folder / 'desktop.ini') & 6, 6)
        self.store.apply(self.folder, self.icon)
        self.assertEqual(len(list(self.folder.glob('*.ico'))), 1)
        self.store.restore(self.folder)
        self.assertEqual(core.attrs(self.folder), self.before)
        self.assertEqual(list(self.folder.iterdir()), [self.user_file])
        self.assertEqual(self.user_file.read_bytes(), b'user content')
        self.assertFalse(self.store.load()['folders'])

    def test_original_ini_preserved_exactly(self):
        ini = self.folder / 'desktop.ini'
        original = ('; keep comments\r\n[.ShellClassInfo]\r\nIconFile=old.ico\r\nIconIndex=2\r\nInfoTip=我的文件\r\n[Other]\r\nKey=value\r\n').encode('utf-16')
        ini.write_bytes(original)
        core.setattrs(ini, 1 | 2 | 4)
        original_attrs = core.attrs(ini)
        self.store.apply(self.folder, self.icon)
        modified = ini.read_bytes().decode('utf-16')
        self.assertIn('InfoTip=我的文件', modified)
        self.assertIn('; keep comments', modified)
        self.assertNotIn('IconFile=', modified)
        self.store.restore(self.folder)
        self.assertEqual(ini.read_bytes(), original)
        self.assertEqual(core.attrs(ini), original_attrs)

    def test_external_changes_refused(self):
        self.store.apply(self.folder, self.icon)
        ini = self.folder / 'desktop.ini'
        changed = ini.read_bytes() + b'new change'
        core.write_bytes(ini, changed)
        with self.assertRaises(ValueError):
            self.store.restore(self.folder)
        self.assertEqual(ini.read_bytes(), changed)
        self.assertEqual(len(self.store.load()['folders']), 1)

    def test_restore_all_only_tracked(self):
        other = self.root / 'untouched'
        other.mkdir()
        (other / 'desktop.ini').write_bytes(b'original')
        self.store.apply(self.folder, self.icon)
        self.assertEqual(self.store.restore_all(), (1, []))
        self.assertEqual((other / 'desktop.ini').read_bytes(), b'original')
        with self.assertRaises(ValueError):
            self.store.restore(other)

    def test_interrupted_apply_is_recoverable(self):
        original_setattrs = core.setattrs
        def fail_on_ini(path, value):
            if Path(path).name == 'desktop.ini':
                raise OSError('simulated failure')
            return original_setattrs(path, value)
        with patch('core.setattrs', side_effect=fail_on_ini):
            with self.assertRaises(OSError):
                self.store.apply(self.folder, self.icon)
        self.assertEqual(next(iter(self.store.load()['folders'].values()))['state'], 'pending')
        self.store.restore(self.folder)
        self.assertEqual(list(self.folder.iterdir()), [self.user_file])

    def test_corrupt_registry_is_not_overwritten(self):
        self.store.registry.write_text('broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.apply(self.folder, self.icon)
        self.assertEqual(self.store.registry.read_text(), 'broken')
        self.assertEqual(list(self.folder.iterdir()), [self.user_file])

    def test_changed_icon_is_not_deleted(self):
        self.store.apply(self.folder, self.icon)
        icon = next(self.folder.glob('*.ico'))
        core.write_bytes(icon, b'other content')
        with self.assertRaises(ValueError):
            self.store.restore(self.folder)
        self.assertEqual(icon.read_bytes(), b'other content')


if __name__ == '__main__':
    unittest.main()
