"""Модели данных для платформы обмена знаниями МШП."""

import base64
import logging
import re

from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


logger = logging.getLogger(__name__)


def is_latin(text):
    """Проверяет, состоит ли строка только из латинских букв, цифр, пробелов и дефисов.

    Используется для валидации текстовых полей, где не допускается кириллица
    (например, никнейм или slug).

    Args:
        text: строка для проверки.

    Returns:
        bool: True, если строка соответствует шаблону, иначе False.
    """
    pattern = r'^[a-zA-Z0-9\s\-]+$'
    result = bool(re.match(pattern, text.strip()))
    logger.debug("is_latin(%r)=%s", text, result)
    return result


def encode_to_base64url(text):
    """Кодирует текст в Base64 URL-safe без завершающих символов '='.

    Применяется для создания уникального slug тега, безопасного для URL.

    Args:
        text: исходная строка (например, название тега).

    Returns:
        str: закодированная строка без padding.
    """
    encoded = base64.urlsafe_b64encode(text.encode('utf-8')).decode('utf-8')
    encoded = encoded.rstrip('=')
    logger.debug("encode_to_base64url input=%r output=%r", text, encoded)
    return encoded


def decode_from_base64url(encoded_text):
    """Декодирует Base64 URL-safe строку обратно в исходный текст.

    Используется для получения оригинального названия тега из slug.

    Args:
        encoded_text: закодированная строка (может быть без padding).

    Returns:
        str: декодированная строка.
    """
    padding_needed = 4 - (len(encoded_text) % 4)
    if padding_needed != 4:
        encoded_text += '=' * padding_needed
    decoded = base64.urlsafe_b64decode(encoded_text).decode('utf-8')
    logger.debug("decode_from_base64url output=%r", decoded)
    return decoded


class Tag(models.Model):
    """Тег для классификации статей и вопросов.

    Каждый тег имеет уникальное название и автоматически генерируемый
    URL-безопасный slug на основе Base64. Используется для фильтрации контента.
    """

    name = models.CharField("Название тега", max_length=50, unique=True)
    slug = models.SlugField("URL-метка", unique=True, max_length=100)

    class Meta:
        """Настройки модели Тег."""

        ordering = ['name']
        verbose_name = 'Тег'
        verbose_name_plural = 'Теги'

    def __str__(self):
        """Возвращает название тега."""
        return str(self.name)

    def get_absolute_url(self):
        """Возвращает URL списка статей, отфильтрованных по данному тегу."""
        return reverse('platform_app:articles_by_tag', kwargs={'slug': self.slug})

    def save(self, *args, **kwargs):
        """Переопределяет сохранение: автоматически генерирует slug из name."""
        self.slug = encode_to_base64url(self.name)
        logger.debug("Saving tag name=%r slug=%r", self.name, self.slug)
        super().save(*args, **kwargs)


class Article(models.Model):
    """Статья или вопрос на платформе.

    Может быть как обычной статьей, так и вопросом (если is_question=True).
    Поддерживает теги, автора и систему лайков. Вопрос можно закрыть (is_closed).
    """

    title = models.CharField("Заголовок", max_length=200)
    content = models.TextField("Содержание")
    is_question = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    author = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='articles')
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    tags = models.ManyToManyField(
        Tag, blank=True, related_name='articles', verbose_name="Теги")

    class Meta:
        """Настройки модели Статья/Вопрос."""

        ordering = ['-created_at']

    def __str__(self):
        """Возвращает заголовок статьи."""
        return str(self.title)

    @property
    def total_likes(self):
        """Возвращает общее количество лайков статьи."""
        return self.likes.count()


class Comment(models.Model):
    """Комментарий к статье или ответу на вопрос.

    Поддерживает ветвление (ответы на комментарии) через поле parent.
    Автором может быть зарегистрированный пользователь или аноним (author_name).
    Комментарий можно отметить как правильный ответ (is_correct) в режиме Q&A.
    """

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='comments'
    )
    text = models.TextField("Текст комментария")
    created_at = models.DateTimeField(auto_now_add=True)
    is_correct = models.BooleanField(default=False)

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )

    @property
    def level(self):
        """Вычисляет уровень вложенности комментария (0 – верхний уровень)."""
        level = 0
        parent = self.parent
        while parent:
            level += 1
            parent = parent.parent
        return level

    class Meta:
        """Настройки модели Комментарий."""

        ordering = ['created_at']

    def __str__(self):
        """Возвращает строку с указанием статьи, к которой написан комментарий."""
        return f'Comment on {self.article}'

    @property
    def is_reply(self):
        """Возвращает True, если комментарий является ответом на другой комментарий."""
        return self.parent is not None

    @property
    def total_likes(self):
        """Возвращает количество лайков на этом комментарии."""
        return self.reactions.filter(reaction='like').count()

    @property
    def total_dislikes(self):
        """Возвращает количество дизлайков на этом комментарии."""
        return self.reactions.filter(reaction='dislike').count()


class Like(models.Model):
    """Лайк статьи, поставленный пользователем.

    Уникальная пара (user, article) гарантирует один голос от одного пользователя.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Настройки модели Лайк статьи."""

        unique_together = ('user', 'article')

    def __str__(self):
        """Возвращает описание вида 'username liked Название статьи'."""
        return f'{self.user} liked {self.article}'


class CommentLike(models.Model):
    """Реакция (лайк/дизлайк) на комментарий.

    Позволяет пользователям выражать одобрение или неодобрение ответов.
    Один пользователь может поставить только одну реакцию на комментарий.
    """

    class ReactionType(models.TextChoices):
        """Типы реакций на комментарий."""
        LIKE = 'like'
        DISLIKE = 'dislike'

    comment = models.ForeignKey(
        'Comment', on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='comment_reactions')
    reaction = models.CharField(max_length=10, choices=ReactionType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Настройки модели Реакция на комментарий."""

        unique_together = ['comment', 'user']

    def __str__(self):
        """Возвращает строку с информацией о реакции пользователя."""
        return f'{self.user} {self.reaction} on {self.comment}'


class UserProfile(models.Model):
    """Дополнительный профиль пользователя платформы."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    role = models.CharField("Роль", max_length=100, blank=True, null=True)

    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name='Аватар'
    )

    @property
    def total_correct_answers(self):
        """Возвращает количество верных ответов, данных пользователем"""
        return self.user.comments.filter(is_correct=True).count()

    def __str__(self):
        return f"{self.user.username} - {self.role}"
