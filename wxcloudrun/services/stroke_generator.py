import shutil
from pathlib import Path

from django.conf import settings
from PIL import Image

from wxcloudrun.services.hanzi_strokes import load_char_data, render_png


def generate_level_assets(level):
    level_dir = Path(settings.MEDIA_ROOT) / 'levels' / str(level.id)
    if level_dir.exists():
        shutil.rmtree(level_dir)
    level_dir.mkdir(parents=True, exist_ok=True)

    chars = []
    for index, char in enumerate(level.source_text):
        char_key = f'c{index + 1}'
        char_dir = level_dir / 'chars' / char_key
        char_dir.mkdir(parents=True, exist_ok=True)
        data = load_char_data(char, None, Path(settings.BASE_DIR) / 'cache')
        strokes = data.get('strokes') or []
        if not strokes:
            raise ValueError(f'没有找到「{char}」的笔画数据')

        full_path = char_dir / 'full.png'
        render_png([(stroke, '#d9d9d9') for stroke in strokes], full_path, 512)

        stroke_items = []
        for stroke_index, stroke in enumerate(strokes):
            stroke_path = char_dir / f'stroke_{stroke_index + 1:02d}.png'
            render_png([(stroke, '#ff8a00')], stroke_path, 512)
            stroke_items.append({
                'stroke_key': f's{stroke_index + 1}',
                'stroke_index': stroke_index + 1,
                'image': media_relative_path(stroke_path),
                'bounds': calculate_bounds(stroke_path),
            })

        chars.append({
            'char_key': char_key,
            'char_text': char,
            'full_image': media_relative_path(full_path),
            'stroke_count': len(strokes),
            'sort_order': index + 1,
            'strokes': stroke_items,
        })

    return chars


def media_relative_path(path):
    return str(Path(path).relative_to(settings.MEDIA_ROOT)).replace('\\', '/')


def calculate_bounds(image_path):
    image = Image.open(image_path).convert('RGBA')
    width, height = image.size
    pixels = image.load()
    min_x, min_y = width, height
    max_x, max_y = -1, -1

    for y in range(height):
        for x in range(width):
            if pixels[x, y][3] > 18:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

    if max_x < 0:
        return {'x': 0, 'y': 0, 'w': 0, 'h': 0}

    return {
        'x': round(min_x / width, 4),
        'y': round(min_y / height, 4),
        'w': round((max_x - min_x + 1) / width, 4),
        'h': round((max_y - min_y + 1) / height, 4),
    }
