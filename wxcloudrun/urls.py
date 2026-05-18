from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, re_path

from wxcloudrun import views


urlpatterns = [
    path('', views.index),
    path('admin/login', views.admin_login_page),
    path('admin/logout', views.admin_logout),
    path('admin/levels', views.admin_levels),
    path('admin/levels/new', views.admin_level_editor),
    path('admin/levels/<int:level_id>', views.admin_level_editor),
    path('api/admin/levels', views.admin_levels_api),
    path('api/admin/levels/<int:level_id>', views.admin_level_api),
    path('api/admin/levels/<int:level_id>/generate', views.admin_generate_level),
    path('api/admin/levels/<int:level_id>/answers', views.admin_answers_api),
    path('api/admin/levels/<int:level_id>/answers/<int:answer_id>', views.admin_answer_api),
    path('api/admin/levels/<int:level_id>/publish', views.admin_publish_level),
    path('api/game/login', views.game_login),
    path('api/game/levels', views.game_levels),
    path('api/game/levels/<int:level_id>', views.game_level_detail),
    path('api/game/progress', views.game_progress),
    path('api/count', views.counter),
    re_path(r'^api/count/?$', views.counter),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
