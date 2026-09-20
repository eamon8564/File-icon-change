from pathlib import Path
from io import BytesIO
from PIL import Image, ImageDraw, ImageColor, ImageChops, ImageFilter
ROOT = Path(__file__).resolve().parent
SIZES = [(n,n) for n in (16,32,48,64,128,256)]

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

def png_bytes(image):
    stream = BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()

def read_icon_image(path):
    with Image.open(path) as image:
        if image.format not in ('PNG', 'ICO', 'ICNS'):
            raise ValueError('请选择 PNG、ICO 或 ICNS 图片。')
        return image.convert('RGBA')

def icns_bytes(image):
    image = image.convert('RGBA')
    ratio = min(1024 / image.width, 1024 / image.height)
    size = (max(1, round(image.width*ratio)), max(1, round(image.height*ratio)))
    canvas = Image.new('RGBA', (1024, 1024))
    canvas.alpha_composite(image.resize(size, Image.Resampling.LANCZOS), ((1024-size[0])//2, (1024-size[1])//2))
    stream = BytesIO()
    canvas.save(stream, format='ICNS')
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


