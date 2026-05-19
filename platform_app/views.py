"""Представления приложения."""

import base64
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Q
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.template.loader import get_template
from xhtml2pdf import pisa

from .models import Article, Comment, CommentLike, Like, Tag, UserProfile
from .profanity_filter import find_banned_words
from .forms import (
    SignUpForm,
    UserUpdateForm,
    ProfileUpdateForm,
    StyledPasswordChangeForm
)

logger = logging.getLogger(__name__)


@login_required
def create_tag(request):
    """Создание тега."""

    logger.info("create_tag called by user=%s method=%s",
                request.user, request.method)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        logger.debug("Tag submission payload: name=%r", name)

        if not name:
            logger.warning(
                "create_tag validation failed: empty tag name user=%s", request.user)
            messages.error(request, 'Пожалуйста, введите название категории.')
            return render(request, 'platform_app/create_tag.html')

        found_words = find_banned_words(name)
        if found_words:
            logger.warning(
                "create_tag profanity detected words=%s user=%s",
                found_words,
                request.user
            )
            messages.error(request, 'Название содержит запрещённые слова')
            return render(request, 'platform_app/create_tag.html')

        if Tag.objects.filter(name__iexact=name).exists():
            logger.info("create_tag duplicate ignored: %s", name)
            messages.warning(request, f'Категория "{name}" уже существует!')
        else:
            tag = Tag.objects.create(name=name)
            logger.info("Tag created id=%s slug=%s by user=%s",
                        tag.pk, tag.slug, request.user)
            messages.success(
                request, f'Категория "{tag.name}" успешно создана!')
            return redirect('platform_app:articles_by_tag', tag_slug=tag.slug)

    return render(request, 'platform_app/create_tag.html')


def article_list(request, tag_slug=None):
    """Список статей."""

    logger.debug("article_list called tag_slug=%s", tag_slug)
    articles = Article.objects.all()
    tag = None

    if tag_slug:
        tag = get_object_or_404(Tag, slug=tag_slug)
        articles = articles.filter(tags=tag)

    tags = Tag.objects.all().order_by('slug')

    if request.user.is_authenticated:
        logger.debug(
            "article_list result stats for user=%s: articles=%s tags=%s",
            request.user,
            articles.count(),
            tags.count(),
        )

    return render(request, 'platform_app/article_list.html', {
        'articles': articles,
        'tag': tag,
        'tags': tags,
    })

def export_article_pdf(request, pk):
    article = get_object_or_404(Article, pk=pk)

    template = get_template('platform_app/article_pdf.html')

    html = template.render({
        'article': article
    })

    response = HttpResponse(content_type='application/pdf')

    response['Content-Disposition'] = (
        f'attachment; filename="{article.title}.pdf"'
    )

    pisa_status = pisa.CreatePDF(
        html,
        dest=response
    )

    if pisa_status.err:
        return HttpResponse(
            'Ошибка при генерации PDF',
            status=500
        )

    return response


def comment_block(temp, comment):
    """Рекурсивно упорядочивает комментарии и ответы к ним"""

    temp.append(comment)
    for comment_child in comment.replies.order_by('is_correct', 'created_at').reverse():
        comment_block(temp, comment_child)


def article_detail(request, pk):
    """Детальная страница статьи."""

    logger.debug("article_detail requested pk=%s user=%s", pk, request.user)
    article = get_object_or_404(Article, pk=pk)

    all_comments = article.comments.filter(parent=None).order_by(
        'is_correct', 'created_at').reverse()
    temp = []
    for comment in all_comments:
        comment_block(temp, comment)

    is_liked = False
    if request.user.is_authenticated:
        is_liked = Like.objects.filter(
            user=request.user, article=article).exists()

    logger.debug(
        "article_detail loaded article_id=%s comments=%s liked=%s",
        article.pk,
        all_comments.count(),
        is_liked,
    )

    return render(request, 'platform_app/article_detail.html', {
        'article': article,
        'all_comments': temp,
        'is_liked': is_liked,
    })


def signup(request):
    """Регистрация пользователя."""

    logger.info("signup called method=%s", request.method)

    if request.method == 'POST':
        storage = messages.get_messages(request)
        storage.used = True

        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username', '')
            password = form.cleaned_data.get('password1', '')
            role_data = form.cleaned_data.get('role', '')

            logger.debug(
                "signup validated username=%s role_present=%s", username, bool(role_data))

            found_words_username = find_banned_words(username)
            found_words_password = find_banned_words(password)
            found_words_role = find_banned_words(role_data)

            if found_words_username or found_words_password or found_words_role:
                logger.warning(
                    "signup rejected due to profanity username_words=%s password_words=%s role_words=%s",
                    found_words_username,
                    found_words_password,
                    found_words_role,
                )
                messages.error(
                    request,
                    'Имя пользователя, пароль или роль содержат запрещённые слова'
                )
                return render(request, 'platform_app/signup.html', {'form': form})

            user = form.save()
            UserProfile.objects.update_or_create(
                user=user, defaults={'role': role_data})

            login(request, user)
            logger.info("signup successful user_id=%s username=%s",
                        user.pk, user.username)
            messages.success(request, "Регистрация прошла успешно!")
            return redirect('platform_app:article_list')

        logger.warning("signup form invalid errors=%s", form.errors.as_json())
    else:
        form = SignUpForm()

    return render(request, 'platform_app/signup.html', {'form': form})


@login_required
def article_create(request):
    """Создание статьи."""

    logger.info("article_create called user=%s method=%s",
                request.user, request.method)
    existing_tags = Tag.objects.all().order_by('slug')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        is_question = request.POST.get('is_question', '').strip()
        tag_names = request.POST.get('tags', '').strip()

        logger.debug(
            "article_create payload title_len=%s content_len=%s is_question=%s tag_names=%r",
            len(title),
            len(content),
            bool(is_question),
            tag_names,
        )

        if not title or not content:
            logger.warning(
                "article_create validation failed: empty title/content user=%s",
                request.user
            )
            messages.error(
                request, 'Пожалуйста, заполните все поля для публикации.')
            return render(request, 'platform_app/create_article.html', {
                'existing_tags': existing_tags,
                'form': {
                    'title': {'value': title},
                    'content': {'value': content},
                    'tags': {'value': tag_names},
                    'is_question': {'checked': is_question},
                },
            })

        found_words = find_banned_words(f"{title} {content} {tag_names}")
        if found_words:
            logger.warning(
                "article_create profanity detected words=%s user=%s",
                found_words,
                request.user
            )
            messages.error(request, 'Публикация содержит запрещённые слова')
            return render(request, 'platform_app/create_article.html', {
                'existing_tags': existing_tags,
                'form': {
                    'title': {'value': title},
                    'content': {'value': content},
                    'tags': {'value': tag_names},
                    'is_question': {'checked': is_question},
                },
            })

        article = Article.objects.create(
            title=title,
            content=content,
            author=request.user,
            is_question=is_question,
        )

        created_tags = []
        if tag_names:
            for tag_name in tag_names.split(','):
                tag_name = tag_name.strip()
                if not tag_name:
                    continue

                tag = Tag.objects.filter(name__iexact=tag_name).first()
                if not tag:
                    tag = Tag.objects.create(name=tag_name)
                    created_tags.append(tag.name)

                article.tags.add(tag)

        logger.info(
            "article_create success article_id=%s user=%s created_tags=%s",
            article.pk,
            request.user,
            created_tags,
        )
        messages.success(request, 'Статья успешно создана!')
        return redirect('platform_app:article_detail', pk=article.pk)

    return render(request, 'platform_app/create_article.html', {'existing_tags': existing_tags})


@login_required
@require_POST
def toggle_like(request, pk):
    """Работает по принципу toggle: первый клик ставит лайк, второй — убирает.
    Доступно только авторизованным пользователям.

    Args:
        request: HttpRequest (POST).
        pk: первичный ключ статьи.

    Returns:
        Редирект на страницу статьи.
    """

    article = get_object_or_404(Article, pk=pk)
    like, created = Like.objects.get_or_create(
        user=request.user, article=article)
    if not created:
        like.delete()
        logger.info("toggle_like removed user=%s article_id=%s",
                    request.user, article.pk)
    else:
        logger.info("toggle_like added user=%s article_id=%s",
                    request.user, article.pk)
    return redirect('platform_app:article_detail', pk=article.pk)


@login_required
@require_POST
def close_question(request, pk):
    """Доступно только автору вопроса (или модератору – логика проверки может быть расширена).
    После закрытия вопрос больше не ожидает новых ответов.

    Args:
        request: HttpRequest (POST).
        pk: первичный ключ статьи-вопроса.

    Returns:
        Редирект на страницу вопроса.
    """

    article = get_object_or_404(Article, pk=pk)
    article.is_closed = True
    article.save()
    logger.info("Question closed article_id=%s by user=%s",
                article.pk, request.user)
    return redirect('platform_app:article_detail', pk=article.pk)


@login_required
@require_POST
def open_question(request, pk):
    """Снимает флаг is_closed, чтобы снова принимать ответы.

    Args:
        request: HttpRequest (POST).
        pk: первичный ключ статьи-вопроса.

    Returns:
        Редирект на страницу вопроса.
    """

    article = get_object_or_404(Article, pk=pk)
    article.is_closed = False
    article.save()
    logger.info("Question opened article_id=%s by user=%s",
                article.pk, request.user)
    return redirect('platform_app:article_detail', pk=article.pk)


@login_required
@require_POST
def add_comment(request, pk):
    """Проверяет текст на пустоту и запрещённые слова.
    Автор комментария – текущий пользователь.

    Args:
        request: HttpRequest (POST с полем 'text').
        pk: первичный ключ статьи.

    Returns:
        Редирект на страницу статьи.
    """

    article = get_object_or_404(Article, pk=pk)
    text = request.POST.get('text')

    if not text:
        logger.warning(
            "add_comment rejected: empty text article_id=%s user=%s",
            article.pk,
            request.user
        )
        messages.error(request, 'Текст комментария не может быть пустым')
        return redirect('platform_app:article_detail', pk=article.pk)

    found_words = find_banned_words(text)
    if found_words:
        logger.warning(
            "add_comment profanity detected article_id=%s user=%s words=%s",
            article.pk,
            request.user,
            found_words,
        )
        messages.error(request, 'Комментарий содержит запрещённые слова')
        return redirect('platform_app:article_detail', pk=article.pk)

    comment = Comment.objects.create(
        article=article, user=request.user, text=text)
    logger.info("Comment created id=%s article_id=%s user=%s",
                comment.pk, article.pk, request.user)
    messages.success(request, 'Комментарий добавлен!')
    return redirect('platform_app:article_detail', pk=article.pk)


@login_required
@require_POST
def toggle_comment_reaction(request, comment_id):
    """Если ранее уже была такая же реакция – удаляется,
    если другая – заменяется. Нельзя поставить лайк и дизлайк одновременно.

    Args:
        request: HttpRequest (POST с полем 'reaction').
        comment_id: первичный ключ комментария.

    Returns:
        Редирект на страницу статьи, к которой относится комментарий.
    """

    comment = get_object_or_404(Comment, pk=comment_id)
    reaction_type = request.POST.get('reaction')

    if reaction_type not in ['like', 'dislike']:
        logger.warning(
            "toggle_comment_reaction invalid reaction=%r user=%s comment_id=%s",
            reaction_type,
            request.user,
            comment_id,
        )
        return redirect('platform_app:article_detail', pk=comment.article.pk)

    reaction, created = CommentLike.objects.get_or_create(
        comment=comment,
        user=request.user,
        defaults={'reaction': reaction_type},
    )

    if not created:
        if reaction.reaction == reaction_type:
            reaction.delete()
            logger.info(
                "Comment reaction removed user=%s comment_id=%s reaction=%s",
                request.user,
                comment.pk,
                reaction_type,
            )
        else:
            reaction.reaction = reaction_type
            reaction.save()
            logger.info(
                "Comment reaction changed user=%s comment_id=%s reaction=%s",
                request.user,
                comment.pk,
                reaction_type,
            )
    else:
        logger.info(
            "Comment reaction created user=%s comment_id=%s reaction=%s",
            request.user,
            comment.pk,
            reaction_type,
        )

    return redirect('platform_app:article_detail', pk=comment.article.pk)


@login_required
@require_POST
def add_comment_reply(request, comment_id):
    """Создаёт новый комментарий с привязкой к родительскому (parent).
    Проверяет текст на пустоту и запрещённые слова.

    Args:
        request: HttpRequest (POST с полем 'text').
        comment_id: первичный ключ родительского комментария.

    Returns:
        Редирект на страницу статьи с этим комментарием.
    """

    parent_comment = get_object_or_404(Comment, pk=comment_id)
    text = request.POST.get('text')

    if not text:
        logger.warning(
            "add_comment_reply rejected empty text user=%s parent=%s",
            request.user,
            comment_id
        )
        messages.error(request, 'Текст ответа не может быть пустым')
        return redirect('platform_app:article_detail', pk=parent_comment.article.pk)

    found_words = find_banned_words(text)
    if found_words:
        logger.warning(
            "add_comment_reply profanity detected user=%s parent=%s words=%s",
            request.user,
            comment_id,
            found_words,
        )
        messages.error(request, 'Ответ содержит запрещённые слова')
        return redirect('platform_app:article_detail', pk=parent_comment.article.pk)

    reply = Comment.objects.create(
        article=parent_comment.article,
        user=request.user,
        text=text,
        parent=parent_comment,
    )

    logger.info(
        "Reply created id=%s parent_id=%s user=%s",
        reply.pk,
        parent_comment.pk,
        request.user
    )
    messages.success(request, 'Ответ добавлен!')
    return redirect('platform_app:article_detail', pk=parent_comment.article.pk)


@login_required
@require_POST
def toggle_mark(request, comment_id):
    """Используется в режиме Q&A, чтобы автор вопроса мог выделить решение.
    Переключает флаг is_correct.

    Args:
        request: HttpRequest (POST).
        comment_id: первичный ключ комментария.

    Returns:
        Редирект на страницу статьи.
    """

    comment = get_object_or_404(Comment, pk=comment_id)
    comment.is_correct = not comment.is_correct
    comment.save()

    logger.info(
        "toggle_mark changed comment_id=%s is_correct=%s by user=%s",
        comment.pk,
        comment.is_correct,
        request.user,
    )
    return redirect('platform_app:article_detail', pk=comment.article.pk)


@login_required
def profile(request):
    """Профиль пользователя."""

    articles = request.user.articles.all()

    profile_obj = UserProfile.objects.get_or_create(user=request.user)[0]

    if request.method == 'POST':

        user_form = UserUpdateForm(
            request.POST,
            instance=request.user
        )

        profile_form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=profile_obj
        )

        password_form = StyledPasswordChangeForm(
            request.user,
            request.POST
        )

        form_type = request.POST.get('form_type')

        if form_type == 'profile':

            user_form = UserUpdateForm(
                request.POST,
                instance=request.user
            )

            profile_form = ProfileUpdateForm(
                request.POST,
                request.FILES,
                instance=request.user.profile
            )

            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()

                profile_ = profile_form.save(commit=False)

                profile_.save()

                messages.success(
                    request,
                    'Профиль успешно обновлён!'
                )

                return redirect('platform_app:profile')

        elif form_type == 'avatar':

            cropped_image = request.POST.get('cropped_image')

            if cropped_image:
                profile_: UserProfile = request.user.profile

                format_, imgstr = cropped_image.split(';base64,')

                ext = format_.split('/')[-1]

                file_name = f'{base64.b64encode(request.user.username.encode('utf-8')).decode('utf-8')}_avatar.{ext}'

                profile_.avatar.delete()

                profile_.avatar.save(
                    file_name,
                    ContentFile(base64.b64decode(imgstr)),
                    save=True
                )

                messages.success(
                    request,
                    'Аватар успешно обновлён!'
                )

            return redirect('platform_app:profile')

        elif form_type == 'password':

            if password_form.is_valid():

                user = password_form.save()

                update_session_auth_hash(request, user)

                messages.success(request, 'Пароль успешно изменён!')
                return redirect('platform_app:profile')

            messages.error(request, 'Ошибка смены пароля')

    else:
        user_form = UserUpdateForm(instance=request.user)

        profile_form = ProfileUpdateForm(
            instance=profile_obj
        )

        password_form = StyledPasswordChangeForm(request.user)

    return render(request, 'platform_app/profile_page.html', {
        'articles': articles,
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    })


def search(request):
    """Расширенный поиск с фильтрами"""
    query = request.GET.get('q', '').strip()
    tag_slug = request.GET.get('tag', '').strip()
    author = request.GET.get('author', '').strip()
    sort_by = request.GET.get('sort', '-created_at')

    articles = Article.objects.all()
    tags = Tag.objects.all().order_by('name')
    selected_tag = None

    if query:
        articles = articles.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(tags__name__icontains=query)
        ).distinct()

    if tag_slug:
        selected_tag = get_object_or_404(Tag, slug=tag_slug)
        articles = articles.filter(tags=selected_tag)

    if author:
        articles = articles.filter(
            Q(author__username__icontains=author) |
            Q(author__first_name__icontains=author) |
            Q(author__last_name__icontains=author)
        )

    valid_sort = ['-created_at', 'created_at', 'title', '-title']
    if sort_by in valid_sort:
        articles = articles.order_by(sort_by)

    return render(request, 'platform_app/search.html', {
        'query': query,
        'articles': articles,
        'tags': tags,
        'selected_tag': selected_tag,
        'sort_by': sort_by,
        'author_filter': author,
    })
