import json
import logging
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from wxcloudrun.models import (
    Counters,
    GameUser,
    Level,
    LevelAnswer,
    LevelAnswerPart,
    LevelChar,
    LevelStroke,
    UserProgress,
)
from wxcloudrun.serializers import serialize_level
from wxcloudrun.services.stroke_generator import generate_level_assets


logger = logging.getLogger('log')


def ok(data=None):
    return JsonResponse({'code': 0, 'data': data}, json_dumps_params={'ensure_ascii': False})


def fail(message, code=-1, status=400):
    return JsonResponse({'code': code, 'errorMsg': message}, status=status, json_dumps_params={'ensure_ascii': False})


def json_body(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode('utf-8'))


def index(request, _=None):
    if request.user.is_authenticated:
        return redirect('/admin/levels')
    return redirect('/admin/login')


def admin_login_page(request, _=None):
    if request.method == 'GET':
        return render(request, 'login.html')

    password = request.POST.get('password', '')
    ensure_admin_user()
    user = authenticate(request, username='admin', password=password)
    if not user:
        return render(request, 'login.html', {'error': '密码错误'})

    login(request, user)
    return redirect('/admin/levels')


def admin_logout(request, _=None):
    logout(request)
    return redirect('/admin/login')


def ensure_admin_user():
    if User.objects.filter(username='admin').exists():
        user = User.objects.get(username='admin')
        if not user.check_password(settings.ADMIN_PASSWORD):
            user.set_password(settings.ADMIN_PASSWORD)
            user.save()
        return

    User.objects.create_superuser('admin', '', settings.ADMIN_PASSWORD)


@login_required(login_url='/admin/login')
def admin_levels(request, _=None):
    levels = Level.objects.all()
    return render(request, 'levels.html', {'levels': levels})


@login_required(login_url='/admin/login')
def admin_level_editor(request, level_id=None):
    level = None
    if level_id:
        level = get_object_or_404(Level, id=level_id)
    return render(request, 'level_editor.html', {'level': level})


@csrf_exempt
@login_required(login_url='/admin/login')
def admin_levels_api(request, _=None):
    if request.method == 'GET':
        return ok([serialize_level(level, include_draft=True) for level in Level.objects.all()])

    if request.method != 'POST':
        return fail('请求方式错误', status=405)

    body = json_body(request)
    source_text = ''.join((body.get('sourceText') or '').split())
    if not source_text:
        return fail('原文不能为空')

    level = Level.objects.create(
        source_text=source_text,
        level_type=infer_level_type(source_text),
        pass_count=max(1, int(body.get('passCount') or 1)),
        sort_order=int(body.get('sortOrder') or 0),
    )
    return ok(serialize_level(level, include_draft=True))


@csrf_exempt
@login_required(login_url='/admin/login')
def admin_level_api(request, level_id):
    level = get_object_or_404(Level, id=level_id)

    if request.method == 'GET':
        return ok(serialize_level(level, include_draft=True))

    if request.method != 'PUT':
        return fail('请求方式错误', status=405)

    body = json_body(request)
    level.source_text = ''.join((body.get('sourceText') or level.source_text).split())
    level.level_type = body.get('type') or infer_level_type(level.source_text)
    level.pass_count = max(1, int(body.get('passCount') or level.pass_count))
    level.sort_order = int(body.get('sortOrder') or level.sort_order)
    level.save()
    return ok(serialize_level(level, include_draft=True))


@csrf_exempt
@login_required(login_url='/admin/login')
def admin_generate_level(request, level_id):
    if request.method != 'POST':
        return fail('请求方式错误', status=405)

    level = get_object_or_404(Level, id=level_id)
    with transaction.atomic():
        level.chars.all().delete()
        generated_chars = generate_level_assets(level)
        for char_item in generated_chars:
            level_char = LevelChar.objects.create(
                level=level,
                char_key=char_item['char_key'],
                char_text=char_item['char_text'],
                full_image=char_item['full_image'],
                stroke_count=char_item['stroke_count'],
                sort_order=char_item['sort_order'],
            )
            for stroke_item in char_item['strokes']:
                LevelStroke.objects.create(
                    level_char=level_char,
                    stroke_key=stroke_item['stroke_key'],
                    stroke_index=stroke_item['stroke_index'],
                    image=stroke_item['image'],
                    bounds=stroke_item['bounds'],
                )
    return ok(serialize_level(level, include_draft=True))


@csrf_exempt
@login_required(login_url='/admin/login')
def admin_answers_api(request, level_id):
    level = get_object_or_404(Level, id=level_id)

    if request.method != 'POST':
        return fail('请求方式错误', status=405)

    body = json_body(request)
    word = (body.get('word') or '').strip()
    parts = body.get('parts') or []
    if not word:
        return fail('答案字不能为空')
    if not parts:
        return fail('至少选择一组笔画')

    with transaction.atomic():
        answer_key = make_answer_key(level, word)
        answer = LevelAnswer.objects.create(
            level=level,
            answer_key=answer_key,
            word=word,
            answer_type=body.get('type') or 'normal',
            score=int(body.get('score') or 10),
            sort_order=level.answers.count() + 1,
        )
        for part in parts:
            char_key = part.get('charId')
            stroke_ids = part.get('strokeIds') or []
            if not char_key or not stroke_ids:
                continue
            level_char = get_object_or_404(LevelChar, level=level, char_key=char_key)
            valid_ids = set(level_char.strokes.values_list('stroke_key', flat=True))
            invalid_ids = [stroke_id for stroke_id in stroke_ids if stroke_id not in valid_ids]
            if invalid_ids:
                transaction.set_rollback(True)
                return fail(f'不存在的笔画：{",".join(invalid_ids)}')
            LevelAnswerPart.objects.create(answer=answer, level_char=level_char, stroke_ids=stroke_ids)

    return ok(serialize_level(level, include_draft=True))


@csrf_exempt
@login_required(login_url='/admin/login')
def admin_answer_api(request, level_id, answer_id):
    level = get_object_or_404(Level, id=level_id)
    answer = get_object_or_404(LevelAnswer, level=level, id=answer_id)

    if request.method != 'DELETE':
        return fail('请求方式错误', status=405)

    answer.delete()
    return ok(serialize_level(level, include_draft=True))


@csrf_exempt
@login_required(login_url='/admin/login')
def admin_publish_level(request, level_id):
    if request.method != 'POST':
        return fail('请求方式错误', status=405)

    level = get_object_or_404(Level, id=level_id)
    if not level.chars.exists():
        return fail('请先生成笔画')
    if not level.answers.exists():
        return fail('请至少配置一个答案')
    if level.pass_count > level.answers.count():
        return fail('通关数量不能大于答案数量')

    level.status = 'published'
    level.version += 1
    level.save()
    return ok(serialize_level(level, include_draft=True))


def game_levels(request, _=None):
    levels = Level.objects.filter(status='published')
    return ok([serialize_level(level) for level in levels])


def game_level_detail(request, level_id):
    level = get_object_or_404(Level, id=level_id, status='published')
    return ok(serialize_level(level))


@csrf_exempt
def game_login(request, _=None):
    if request.method != 'POST':
        return fail('请求方式错误', status=405)

    body = json_body(request)
    code = body.get('code')
    if not code:
        return fail('缺少 code')

    if settings.WECHAT_APPID and settings.WECHAT_SECRET:
        session = fetch_wechat_session(code)
        openid = session.get('openid')
        unionid = session.get('unionid', '')
        if not openid:
            return fail('微信登录失败')
    else:
        openid = f'dev_{code}'
        unionid = ''

    user, _ = GameUser.objects.get_or_create(openid=openid, defaults={'unionid': unionid})
    if unionid and user.unionid != unionid:
        user.unionid = unionid
        user.save()
    return ok({'token': user.openid, 'user': serialize_user(user)})


@csrf_exempt
def game_progress(request, _=None):
    if request.method != 'POST':
        return fail('请求方式错误', status=405)

    user = require_game_user(request)
    if not user:
        return fail('未登录', status=401)

    body = json_body(request)
    level = get_object_or_404(Level, id=body.get('levelId'), status='published')
    found_answers = body.get('foundAnswers') or []
    score = int(body.get('score') or 0)
    is_passed = bool(body.get('passed'))

    progress, _ = UserProgress.objects.get_or_create(user=user, level=level)
    progress.found_answers = found_answers
    progress.score = max(progress.score, score)
    if is_passed:
        progress.status = 'passed'
        if not progress.first_pass_at:
            progress.first_pass_at = timezone.now()
    progress.save()
    return ok({'progress': serialize_progress(progress)})


def counter(request, _=None):
    if request.method == 'GET':
        try:
            data = Counters.objects.get(id=1)
            count = data.count
        except Counters.DoesNotExist:
            count = 0
        return ok(count)

    if request.method != 'POST':
        return fail('请求方式错误', status=405)

    body = json_body(request)
    if body.get('action') == 'inc':
        data, _ = Counters.objects.get_or_create(id=1)
        data.count += 1
        data.save()
        return ok(data.count)
    if body.get('action') == 'clear':
        Counters.objects.filter(id=1).delete()
        return ok(0)
    return fail('action参数错误')


def infer_level_type(source_text):
    length = len(source_text)
    if length <= 1:
        return 'single'
    if length == 4:
        return 'idiom'
    return 'multi'


def make_answer_key(level, word):
    base = f'a{level.answers.count() + 1}'
    key = f'{base}_{word}'
    while LevelAnswer.objects.filter(level=level, answer_key=key).exists():
        base = f'a{level.answers.count() + 2}'
        key = f'{base}_{word}'
    return key


def fetch_wechat_session(code):
    query = urllib.parse.urlencode({
        'appid': settings.WECHAT_APPID,
        'secret': settings.WECHAT_SECRET,
        'js_code': code,
        'grant_type': 'authorization_code',
    })
    url = f'https://api.weixin.qq.com/sns/jscode2session?{query}'
    with urllib.request.urlopen(url, timeout=8) as response:
        return json.loads(response.read().decode('utf-8'))


def require_game_user(request):
    token = request.headers.get('X-User-Token') or request.GET.get('token')
    if not token:
        return None
    try:
        return GameUser.objects.get(openid=token)
    except GameUser.DoesNotExist:
        return None


def serialize_user(user):
    return {
        'id': user.id,
        'openid': user.openid,
        'coin': user.coin,
        'energy': user.energy,
        'currentLevelId': user.current_level_id,
    }


def serialize_progress(progress):
    return {
        'levelId': progress.level_id,
        'status': progress.status,
        'foundAnswers': progress.found_answers,
        'score': progress.score,
        'firstPassAt': progress.first_pass_at.isoformat() if progress.first_pass_at else '',
    }
