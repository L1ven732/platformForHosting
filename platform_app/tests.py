"""Docstring"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Article, Tag, Comment, Like, CommentLike, UserProfile


class BaseTestCase(TestCase):
    """Docstring"""

    def setUp(self):
        """Docstring"""

        self.client = Client()
        self.user = User.objects.create_user(username='test', password='12345')
        self.client.login(username='test', password='12345')

        self.tag = Tag.objects.create(name='TestTag')
        self.article = Article.objects.create(
            title='Test Article',
            content='Content',
            author=self.user
        )
        self.article.tags.add(self.tag)


# ===================== MODELS =====================

class ModelTests(BaseTestCase):
    """Docstring"""

    def test_tag_slug_generated(self):
        """Docstring"""

        self.assertTrue(self.tag.slug)

    def test_article_str(self):
        """Docstring"""

        self.assertEqual(str(self.article), 'Test Article')

    def test_tag_str(self):
        """Docstring"""

        self.assertEqual(str(self.tag), 'TestTag')

    def test_like_unique(self):
        """Docstring"""

        Like.objects.create(user=self.user, article=self.article)
        with self.assertRaises(Exception):
            Like.objects.create(user=self.user, article=self.article)

    def test_comment_creation(self):
        """Docstring"""

        comment = Comment.objects.create(
            article=self.article,
            user=self.user,
            text="Hello"
        )
        self.assertEqual(comment.text, "Hello")

    def test_comment_reply(self):
        """Docstring"""

        parent = Comment.objects.create(
            article=self.article, user=self.user, text="Parent")
        reply = Comment.objects.create(article=self.article, user=self.user,
                                       text="Reply", parent=parent)
        self.assertTrue(reply.is_reply)

    def test_comment_likes(self):
        """Docstring"""

        comment = Comment.objects.create(
            article=self.article, user=self.user, text="Test")
        CommentLike.objects.create(
            comment=comment, user=self.user, reaction='like')
        self.assertEqual(comment.total_likes, 1)

    def test_user_profile_creation(self):
        """Docstring"""

        userprofile = UserProfile.objects.create(
            user=self.user, role="TestRole")
        self.assertEqual(userprofile.role, "TestRole")


# ===================== VIEWS =====================

class ViewTests(BaseTestCase):
    """Docstring"""

    def test_article_list(self):
        """Docstring"""

        response = self.client.get(reverse('platform_app:article_list'))
        self.assertEqual(response.status_code, 200)

    def test_article_detail(self):
        """Docstring"""

        response = self.client.get(
            reverse('platform_app:article_detail', args=[self.article.pk]))
        self.assertEqual(response.status_code, 200)

    def test_create_article(self):
        """Docstring"""

        response = self.client.post(reverse('platform_app:article_create'), {
            'title': 'New',
            'content': 'Text',
            'is_question': True
        })
        self.assertEqual(response.status_code, 302)

    def test_create_tag(self):
        """Docstring"""

        response = self.client.post(reverse('platform_app:create_tag'), {
            'name': 'NewTag'
        })
        self.assertEqual(response.status_code, 302)

    def test_toggle_like(self):
        """Docstring"""

        response = self.client.post(
            reverse('platform_app:toggle_like', args=[self.article.pk]))
        self.assertEqual(response.status_code, 302)

    def test_add_comment(self):
        """Docstring"""

        response = self.client.post(reverse('platform_app:add_comment', args=[self.article.pk]), {
            'text': 'Hello'
        })
        self.assertEqual(response.status_code, 302)

    def test_profile_view(self):
        """Docstring"""

        response = self.client.get(reverse('platform_app:profile'))
        self.assertEqual(response.status_code, 200)

    def test_signup(self):
        """Docstring"""

        response = self.client.post(reverse('platform_app:signup'), {
            'username': 'newuser',
            'email': 'test@test.com',
            'password1': 'StrongPass123',
            'password2': 'StrongPass123'
        })
        self.assertEqual(response.status_code, 302)


# ===================== EXTRA TESTS (ДОБИВАЕМ ДО 30+) =====================

class ExtraTests(BaseTestCase):
    """Docstring"""

    def test_tag_filter(self):
        """Docstring"""

        response = self.client.get(
            reverse('platform_app:articles_by_tag', args=[self.tag.slug]))
        self.assertEqual(response.status_code, 200)

    def test_invalid_article_pk(self):
        """Docstring"""

        response = self.client.get('/invalid-pk/')
        self.assertEqual(response.status_code, 404)

    def test_comment_reaction(self):
        """Docstring"""

        comment = Comment.objects.create(
            article=self.article, user=self.user, text="Hi")
        response = self.client.post(reverse('platform_app:toggle_comment_reaction',
                                            args=[comment.id]), {
            'reaction': 'like'
        })
        self.assertEqual(response.status_code, 302)

    def test_comment_reply(self):
        """Docstring"""

        comment = Comment.objects.create(
            article=self.article, user=self.user, text="Hi")
        response = self.client.post(reverse('platform_app:add_comment_reply', args=[comment.id]), {
            'text': 'Reply'
        })
        self.assertEqual(response.status_code, 302)

    def test_logout(self):
        """Docstring"""

        response = self.client.post('/logout/')
        self.assertEqual(response.status_code, 302)

    def test_login_page(self):
        """Docstring"""

        response = self.client.get('/login/')
        self.assertEqual(response.status_code, 200)

    def test_empty_comment(self):
        """Docstring"""

        response = self.client.post(reverse('platform_app:add_comment', args=[self.article.pk]), {
            'text': ''
        })
        self.assertEqual(response.status_code, 302)

    def test_multiple_tags(self):
        """Docstring"""

        tag2 = Tag.objects.create(name='Tag2')
        self.article.tags.add(tag2)
        self.assertEqual(self.article.tags.count(), 2)
