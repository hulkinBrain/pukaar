from django.conf.urls import url, include
from . import views

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^auth/', include('social_django.urls', namespace='social')),
    url(r'^submitQuery/', views.submit_query, name='submit_query'),
    url(r'^submitQueryReply/$', views.expert_view, name='submitQueryReply'),
    url(r'^login/', views.login_view, name='login'),
    url(r'^expert/$', views.expert_view, name='home'),
    url(r'^setExpertView/$', views.set_expert_view, name='setExpertView'),
    url(r'^searchQueryView/$', views.search_query, name='searchQueryView'),
    url(r'^setGroup/$', views.set_group, name='setGroup'),
    url(r'^logout/', views.logout_view, name='logout'),
    url(r'^receiveAudio/', views.receive_audio, name='receive'),
    url(r'^report/$', views.generate_report, name='report'),
    # url(r'^localhostLogin/$', views.localhostLogin, name='locahostLogin'),
    url(r'^replySatisfaction/(?P<replyHash>\w{64})/(?P<queryId>[0-9]+)/$', views.process_reply_satisfaction, name='replySatisfaction')
]