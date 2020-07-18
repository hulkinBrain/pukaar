from django.conf.urls import url, include
from . import views

urlpatterns = [
    url(r'^$', views.index, name='home'),
    url(r'^auth/', include('social_django.urls', namespace='social')),
    url(r'^submitQuery/', views.submit_query, name='submit_query'),
    url(r'^submitFeedback/', views.expert_view, name='submit_feedback'),
    url(r'^login/', views.login_view, name='login'),
    url(r'^expert/', views.expert_view, name='home'),
    url(r'^setExpertView/', views.set_expert_view, name='setExpertView'),
    url(r'^logout/', views.logout_view, name='logout'),
    url(r'^receiveAudio/', views.receive_audio, name='receive')
]