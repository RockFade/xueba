from django.conf import settings


def media_url(path):
    if not path:
        return ''
    if path.startswith('http://') or path.startswith('https://') or path.startswith('/'):
        return path
    return settings.MEDIA_URL + path


def serialize_level(level, include_draft=False):
    if level.status != 'published' and not include_draft:
        return None

    return {
        'id': level.id,
        'sourceText': level.source_text,
        'type': level.level_type,
        'passCount': level.pass_count,
        'sortOrder': level.sort_order,
        'status': level.status,
        'version': level.version,
        'chars': [serialize_char(item) for item in level.chars.all()],
        'answers': [serialize_answer(item) for item in level.answers.all()],
    }


def serialize_char(level_char):
    return {
        'charId': level_char.char_key,
        'char': level_char.char_text,
        'fullImage': media_url(level_char.full_image),
        'strokeCount': level_char.stroke_count,
        'strokes': [serialize_stroke(item) for item in level_char.strokes.all()],
    }


def serialize_stroke(stroke):
    return {
        'id': stroke.stroke_key,
        'index': stroke.stroke_index,
        'image': media_url(stroke.image),
        'bounds': stroke.bounds,
    }


def serialize_answer(answer):
    return {
        'dbId': answer.id,
        'id': answer.answer_key,
        'word': answer.word,
        'type': answer.answer_type,
        'score': answer.score,
        'parts': [
            {
                'charId': item.level_char.char_key,
                'strokeIds': item.stroke_ids,
            }
            for item in answer.parts.all()
        ],
    }
