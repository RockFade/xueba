from django.db import models
from django.utils import timezone


class Counters(models.Model):
    count = models.IntegerField(default=0)
    createdAt = models.DateTimeField(default=timezone.now)
    updatedAt = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'Counters'


class Level(models.Model):
    TYPE_CHOICES = (
        ('single', '单字'),
        ('multi', '多字'),
        ('idiom', '成语'),
    )
    STATUS_CHOICES = (
        ('draft', '草稿'),
        ('published', '已发布'),
        ('disabled', '已下架'),
    )

    source_text = models.CharField(max_length=32)
    level_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default='single')
    pass_count = models.PositiveIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='draft')
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'levels'
        ordering = ['sort_order', 'id']


class LevelChar(models.Model):
    level = models.ForeignKey(Level, related_name='chars', on_delete=models.CASCADE)
    char_key = models.CharField(max_length=16)
    char_text = models.CharField(max_length=8)
    full_image = models.CharField(max_length=255)
    stroke_count = models.PositiveIntegerField(default=0)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'level_chars'
        ordering = ['sort_order', 'id']
        unique_together = (('level', 'char_key'),)


class LevelStroke(models.Model):
    level_char = models.ForeignKey(LevelChar, related_name='strokes', on_delete=models.CASCADE)
    stroke_key = models.CharField(max_length=16)
    stroke_index = models.PositiveIntegerField()
    image = models.CharField(max_length=255)
    bounds = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'level_strokes'
        ordering = ['stroke_index']
        unique_together = (('level_char', 'stroke_key'),)


class LevelAnswer(models.Model):
    ANSWER_TYPE_CHOICES = (
        ('normal', '常规'),
        ('rare', '隐藏'),
    )

    level = models.ForeignKey(Level, related_name='answers', on_delete=models.CASCADE)
    answer_key = models.CharField(max_length=64)
    word = models.CharField(max_length=8)
    answer_type = models.CharField(max_length=16, choices=ANSWER_TYPE_CHOICES, default='normal')
    score = models.PositiveIntegerField(default=10)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'level_answers'
        ordering = ['sort_order', 'id']
        unique_together = (('level', 'answer_key'),)


class LevelAnswerPart(models.Model):
    answer = models.ForeignKey(LevelAnswer, related_name='parts', on_delete=models.CASCADE)
    level_char = models.ForeignKey(LevelChar, related_name='+', on_delete=models.CASCADE)
    stroke_ids = models.JSONField(default=list)

    class Meta:
        db_table = 'level_answer_parts'


class GameUser(models.Model):
    openid = models.CharField(max_length=128, unique=True)
    unionid = models.CharField(max_length=128, blank=True, default='')
    nickname = models.CharField(max_length=128, blank=True, default='')
    avatar = models.CharField(max_length=255, blank=True, default='')
    coin = models.PositiveIntegerField(default=0)
    energy = models.PositiveIntegerField(default=20)
    current_level = models.ForeignKey(Level, null=True, blank=True, related_name='+', on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'game_users'


class UserProgress(models.Model):
    STATUS_CHOICES = (
        ('playing', '进行中'),
        ('passed', '已通关'),
    )

    user = models.ForeignKey(GameUser, related_name='progress', on_delete=models.CASCADE)
    level = models.ForeignKey(Level, related_name='+', on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default='playing')
    found_answers = models.JSONField(default=list, blank=True)
    score = models.PositiveIntegerField(default=0)
    first_pass_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_progress'
        unique_together = (('user', 'level'),)
