"""Docstring"""

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


app_name = 'platform_app'

urlpatterns = [
    path('', views.article_list, name='article_list'),
    path('login/', auth_views.LoginView.as_view(template_name='platform_app/login.html'),
         name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('signup/', views.signup, name='signup'),
    path('profile/', views.profile, name='profile'),
    path('create/', views.article_create, name='article_create'),
    path('tag/<slug:tag_slug>/', views.article_list, name='articles_by_tag'),
    path('create-tag/', views.create_tag, name='create_tag'),
    path('<int:pk>/', views.article_detail, name='article_detail'),

    path('<int:pk>/like/', views.toggle_like, name='toggle_like'),
    path('<int:pk>/close/', views.close_question, name='close_question'),
    path('<int:pk>/open/', views.open_question, name='open_question'),
    path('<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('comment/<int:comment_id>/reaction/',
         views.toggle_comment_reaction, name='toggle_comment_reaction'),
    path('comment/<int:comment_id>/reply/',
         views.add_comment_reply, name='add_comment_reply'),
    path('comment/<int:comment_id>/mark/',
         views.toggle_mark, name='toggle_mark'),
    path('search/', views.search, name='search'),

]
