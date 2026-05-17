"""Настройка административной панели Django для платформы обмена знаниями МШП.

Содержит регистрацию моделей и кастомизацию их отображения,
поиска, фильтрации и списков в интерфейсе администратора.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Article, Comment, Like, CommentLike, Tag, UserProfile


# Перерегистрируем стандартную модель User, чтобы применить кастомный UserAdmin.
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Административный интерфейс для управления пользователями.

    Расширяет стандартный UserAdmin: добавляет отображение даты регистрации,
    фильтрацию по активности и правам, а также удобную русскоязычную группировку полей.
    """

    list_display = ('username', 'email', 'first_name',
                    'last_name', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {
         'fields': ('first_name', 'last_name', 'email')}),
        ('Права доступа', {'fields': ('is_active', 'is_staff', 'is_superuser',
                                      'groups', 'user_permissions')}),
        ('Важные даты', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Административный интерфейс для тегов (категорий).

    Позволяет просматривать количество статей с каждым тегом,
    выполнять поиск по названию и фильтрацию.
    """

    list_display = ('name', 'slug', 'articles_count')
    list_filter = ('name',)
    search_fields = ('name',)
    readonly_fields = ('articles_count',)

    def articles_count(self, obj):
        """Возвращает количество статей, связанных с данным тегом."""
        return obj.articles.count()

    articles_count.short_description = 'Статей с тегом'


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Административный интерфейс для статей и вопросов.

    Отображает заголовок, автора, дату создания и количество лайков.
    Поддерживает фильтрацию по автору, дате и тегам, а также поиск по тексту.
    """

    list_display = ('title', 'author', 'created_at', 'total_likes_count')
    list_filter = ('created_at', 'author', 'tags')
    search_fields = ('title', 'content', 'author__username')
    readonly_fields = ('created_at', 'total_likes_count')
    filter_horizontal = ('tags',)

    def total_likes_count(self, obj):
        """Возвращает общее количество лайков у статьи."""
        return obj.total_likes()

    total_likes_count.short_description = 'Лайки'


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """Административный интерфейс для комментариев.

    Показывает сокращённый текст, автора, статью, дату и флаг «Ответ».
    Поддерживает поиск по тексту, автору и названию статьи.
    """

    list_display = ('text_short', 'user', 'article',
                    'created_at', 'is_reply')
    list_filter = ('created_at', 'user', 'article')
    search_fields = ('text', 'author__username', 'article__title')
    readonly_fields = ('created_at',)

    def text_short(self, obj):
        """Возвращает первые 50 символов текста комментария с многоточием, если длиннее."""
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text

    text_short.short_description = 'Текст'

    def is_reply(self, obj):
        """Возвращает 'Да', если комментарий является ответом на другой, иначе 'Нет'."""
        return 'Да' if obj.parent else 'Нет'

    is_reply.short_description = 'Ответ'


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    """Административный интерфейс для лайков статей.

    Отображает пользователя, статью и дату установки лайка.
    """

    list_display = ('user', 'article', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'article__title')
    readonly_fields = ('created_at',)


@admin.register(CommentLike)
class CommentLikeAdmin(admin.ModelAdmin):
    """Административный интерфейс для реакций (лайк/дизлайк) на комментарии.

    Позволяет фильтровать по типу реакции и дате, искать по пользователю и тексту комментария.
    """

    list_display = ('user', 'comment', 'reaction', 'created_at')
    list_filter = ('reaction', 'created_at')
    search_fields = ('user__username', 'comment__text')
    readonly_fields = ('created_at',)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Административный интерфейс для профилей пользователей.

    Отображает связку пользователь–роль и позволяет искать по имени пользователя и роли.
    """

    list_display = ('user', 'role')
    search_fields = ('user__username', 'role')
