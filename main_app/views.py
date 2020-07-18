from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.models import User, Group
from django.core.mail import EmailMessage
from django.views.decorators.csrf import csrf_exempt

from google.cloud import speech
from google.cloud.speech import types
from google.oauth2 import service_account

import math
import json
import base64
import os
import re

from main_app.forms import QueryForm, ReplyForm, SetExpertForm
from main_app.models import Query, Expert, Reply
from main_app.transcript_data_extractor import data_extractor

ITEMS_PER_PAGE = 10

def index(request):
    queryForm = QueryForm()
    feedbackForm = ReplyForm()
    context = {'queryForm': queryForm, 'feedbackForm': feedbackForm}
    return render(request, 'index.html', context)


def submit_query(request):
    if request.method == 'POST':
        queryForm = QueryForm(request.POST)
        if queryForm.is_valid():
            if queryForm.cleaned_data['qual_add_info'] != None:
                queryForm.qual_add_info = queryForm.cleaned_data['qual_add_info']
            if queryForm.cleaned_data['qualification'] == "MBBS":
                queryForm.qual_add_info = None
            cd = queryForm.cleaned_data
            new_query = Query(name=cd.get('name'),
                            qualification=cd.get('qualification'),
                            qual_add_info=cd.get('qual_add_info'),
                            practice_type= cd.get('practice_type'),
                            area_of_practice=cd.get('area_of_practice'),
                            mobile_no=cd.get('mobile_no'),
                            email=cd.get('email'),
                            query=cd.get('query'),
                            query_start_time=timezone.now()
                        )
            new_query.save()
            # CREATE STUFF FOR HTML_EMAIL
            subject = "You have a new query"
            html_content = '' \
                           '<p>You have a new Query #' + str(new_query.id) + '</p>'
            print(new_query.email)
            msg = EmailMessage(subject, html_content, to=[new_query.email])
            msg.content_subtype = "html"
            msg.send()
            return HttpResponse("Saved")
        else:
            # print("error")
            # print(queryForm.errors)
            return JsonResponse(dict(queryForm.errors.items()))
    else:
        queryForm = QueryForm()
        feedbackForm = ReplyForm()
        context = {'queryForm': queryForm, 'feedbackForm': feedbackForm}
        return render(request, index(request), context)


def expert_view(request):
    if Expert.objects.filter(user=request.user).count() > 0:
        if request.method == "GET":
            replyForm = ReplyForm()
            expert = Expert.objects.filter(user=request.user).get()
            queries_list = Query.objects.filter(expert_assigned=expert, needReply=True)\
                .values('id', 'name', 'qualification', 'qual_add_info', 'area_of_practice',
                        'email', 'query', 'query_start_time')\
                .order_by('query_start_time')

            noOfPages = int(math.ceil(len(queries_list)/ITEMS_PER_PAGE))

            paginator = Paginator(queries_list, ITEMS_PER_PAGE)
            page = request.GET.get('page')
            if page == None:
                page = 1
            queries = paginator.get_page(page)

            replies = Reply.objects.all()

            context = {'replyForm': replyForm, 'queries': queries, 'replies': replies, 'noOfPages': noOfPages}
            return render(request, 'expert.html', context)

        elif request.method == "POST":
            replyForm = ReplyForm(request.POST)
            if replyForm.is_valid():
                reply = replyForm.cleaned_data["reply"]
                reply_extra = replyForm.cleaned_data['reply_extra']
                queryId = replyForm.cleaned_data['queryId']
                if reply_extra == "" or reply_extra == None:
                    Query.objects.filter(id=queryId).update(needReply=False)
                else:
                    Query.objects.filter(id=queryId).update(expert_assigned=None, needReply=True)
                new_reply = Reply(
                    reply=reply,
                    query=Query.objects.filter(id=queryId).get(),
                    expert=Expert.objects.filter(user=request.user).get(),
                    reply_extra=reply_extra,
                    reply_datetime=timezone.now(),
                )
                new_reply.save()
                return HttpResponse("Feedback sent")
            else:
                return JsonResponse(dict(replyForm.errors.items()))

    else:
        return HttpResponseRedirect('/logout/')


def set_expert_view(request):
    if request.method == "GET":

        pageNo = request.GET.get('pageNo')
        tabNo = request.GET.get('tabNo')

        if pageNo == None and tabNo == None:
            expertNotAssignedQueries = Query.objects.filter(expert_assigned=None)\
                .values('id', 'name', 'qualification', 'qual_add_info', 'email', 'query', 'query_start_time', 'needReply')\
                .order_by('query_start_time')
            noOfPagesExpertNotAssigned = int(math.ceil(len(expertNotAssignedQueries) / ITEMS_PER_PAGE))

            replies = Reply.objects.filter().values('query', 'expert__user__first_name', 'expert__user__last_name', 'expert__user__username', 'reply', 'reply_extra', 'reply_datetime')
            experts = Expert.objects.all().order_by('user__groups__name')
            setExpertForm = SetExpertForm()

            page = 1

            paginator = Paginator(expertNotAssignedQueries, ITEMS_PER_PAGE)
            expertNotAssignedQueries = paginator.get_page(page)

            context = {
                'queries': expertNotAssignedQueries,
                'experts': experts,
                'setExpertForm': setExpertForm,
                'replies': replies,
                'noOfPagesExpertNotAssigned': noOfPagesExpertNotAssigned,
            }

            return render(request, "admin_pages/setExpert.html", context)

        else:
            replies = Reply.objects.filter().values('query', 'expert__user__first_name', 'expert__user__last_name',
                                                    'expert__user__username', 'reply', 'reply_extra', 'reply_datetime')
            experts = Expert.objects.all().order_by('user__groups__name')
            setExpertForm = SetExpertForm()

            context = None
            print(pageNo, tabNo)
            if tabNo == "1":
                expertNotAssignedQueries = Query.objects.filter(expert_assigned=None) \
                    .values('id', 'name', 'qualification', 'qual_add_info', 'email', 'query', 'query_start_time',
                            'needReply') \
                    .order_by('query_start_time')
                noOfPagesExpertNotAssigned = int(math.ceil(len(expertNotAssignedQueries) / ITEMS_PER_PAGE))
                paginator = Paginator(expertNotAssignedQueries, ITEMS_PER_PAGE)
                expertNotAssignedQueries = paginator.get_page(pageNo)

                context = {
                    'queries': expertNotAssignedQueries,
                    'experts': experts, 'setExpertForm': setExpertForm, 'replies': replies,
                    'noOfPagesExpertNotAssigned': noOfPagesExpertNotAssigned,
                }

            if tabNo == "2":
                expertAssignedQueriesNeedReplyTrue = Query.objects.exclude(expert_assigned=None).filter(needReply=True) \
                    .values('id', 'name', 'qualification', 'qual_add_info', 'email', 'expert_assigned', 'query',
                            'needReply', 'query_start_time') \
                    .order_by('-needReply')
                noOfPagesExpertAssignedNeedReplyTrue = int(
                    math.ceil(len(expertAssignedQueriesNeedReplyTrue) / ITEMS_PER_PAGE))
                paginator = Paginator(expertAssignedQueriesNeedReplyTrue, ITEMS_PER_PAGE)
                expertAssignedQueriesNeedReplyTrue = paginator.get_page(pageNo)

                context = {
                    'expertAssignedQueriesNeedReplyTrue': expertAssignedQueriesNeedReplyTrue,
                    'experts': experts, 'setExpertForm': setExpertForm, 'replies': replies,
                    'noOfPagesExpertAssignedNeedReplyTrue': noOfPagesExpertAssignedNeedReplyTrue,
                    'tabNo:': tabNo
                }

            if tabNo == "3":
                expertAssignedQueriesNeedReplyFalse = Query.objects.exclude(expert_assigned=None).filter(needReply=False) \
                    .values('id', 'name', 'qualification', 'qual_add_info', 'email', 'expert_assigned', 'query',
                            'needReply', 'query_start_time') \
                    .order_by('-needReply')
                noOfPagesExpertAssignedNeedReplyFalse = int(math.ceil(len(expertAssignedQueriesNeedReplyFalse) / ITEMS_PER_PAGE))
                paginator = Paginator(expertAssignedQueriesNeedReplyFalse, ITEMS_PER_PAGE)
                expertAssignedQueriesNeedReplyFalse = paginator.get_page(pageNo)

                context = {
                    'expertAssignedQueriesNeedReplyFalse': expertAssignedQueriesNeedReplyFalse,
                    'experts': experts, 'setExpertForm': setExpertForm, 'replies': replies,
                    'noOfPagesExpertAssigned': noOfPagesExpertAssignedNeedReplyFalse,
                    'tabNo:': tabNo
                }

            return render(request, "admin_pages/setExpert.html", context)

    elif request.method == "POST":
        setExpertForm = SetExpertForm(request.POST)
        if setExpertForm.is_valid():
            queryId = setExpertForm.cleaned_data['queryId']
            expertId = setExpertForm.cleaned_data['expertId']
            if queryId == None or expertId == None:
                return HttpResponse("Error")
            else:
                expert = Expert.objects.filter(id=expertId).get()
                Query.objects.filter(pk=queryId).update(expert_assigned=expert, needReply=True)

                # CREATE STUFF FOR HTML_EMAIL
                subject = "You have a new query"
                html_content = '' \
                               '<p>You have a new Query #'+str(queryId)+'</p>'
                print(expert.user.email)
                msg = EmailMessage(subject, html_content, to=[expert.user.email])
                msg.content_subtype = "html"
                msg.send()

        else:
            print(setExpertForm.errors)
        return HttpResponse("Success")

@csrf_exempt
def receive_audio(request):
    if request.method == 'POST':

        # JSON DATA GOT FROM ZAPIER
        json_data = json.loads(request.body)
        decoded = base64.b64decode(json_data['flac_audio_b64'])

        SCOPES = ['https://www.googleapis.com/auth/cloud-platform']

        # json_creds = json.loads(base64.b64decode(os.environ["G_AUTH"]).decode())
        json_creds = json.loads(base64.b64decode("eyJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsICJwcm9qZWN0X2lkIjogInNwZWVjaC1hcGktcHJvaiIsICJwcml2YXRlX2tleV9pZCI6ICI0NjdjZDg3NTZiZDFiOWQ5NGMxY2UzY2M3ODg3YTAyZDIzOTc4ZGEzIiwgInByaXZhdGVfa2V5IjogIi0tLS0tQkVHSU4gUFJJVkFURSBLRVktLS0tLVxuTUlJRXZRSUJBREFOQmdrcWhraUc5dzBCQVFFRkFBU0NCS2N3Z2dTakFnRUFBb0lCQVFDazNnb0ZHTW1qdkF5UVxuNG9ycU9sTlpNQVVmQzd0cTlUWG1EVFhLeGdJcU5MSEs5ZitwcVZGOTFnVk5ZdGhMaitUb0NXQ0hacjM1Ym0vT1xuZklCbGR0U2kwYUJBeTN2WDkwZXdVeXJUYjRWckkyaVFYOEJrbHVDa0hOQnhoMGRjZ2lQSldXN1NpZklCRko1a1xuaFJ3aHhMNTgxSitQcWo1Z3NUNjZHbFE1NzhuZ1ZlS1dPQ3VKdkhNTVJyTGJmTWozZmJ1UUVIUzRIRTJ3cUl2M1xuZ2cxTnB5WkZUMTNpV0hvNHExNjVRekQ4NHptanVnelRSaW5lQkgzcDY0d1prYVM1TmxYb2RXRU81SzRWVUtRc1xuT3hxSVRibk5yeDN5SFJISnlFcTFzVEZlMWcxMXV6ZmN4Sk9UcjZtdjVxenpPRWFleWxycjlxSVNDbkZoKy9Dc1xuUWlmYXB2bWZBZ01CQUFFQ2dnRUFPekRBZGkzOURyelA0aUNEY1M1NWlCYTJiL3Y5VUp3eXVxSlpnckJ1VElyWVxubmg2TnFITHluL1A3dVZuWWYrQnNkV1lRY3V4UEhrTW8vd0F4OUx1aUFjYXkrekJUQ1NsdFluK3BhM21wYzlxbFxuaXRmbHNmZDlOVTVuQTZ0bTBtNml2SUpRU0dSZ0wwVWd6TVFCWXBwSkxYWUV4MForMktZcCtCVEYwbnNsaGxXYVxudXo5L0xjUExueU0yV2lTZzRNZWZaMHRxRWFuUUZiL3dkVzBMZ3lkOXF5bWUvYXcxbkJyMC9HOGQ3TXFicHRwQVxuRjN2NEdWN29vcEJpVmxWSW9CcEQwUU5LNStoZ2R5dC9vU3EzL0tpb214bi9lR2lway9JYWNpb2N4RGVxaFlzR1xuMUtYc2dkd3QyRktrU0R1MFl4eXNLa2RUZHRFN0NhLzlGYUlPZ3NQRTJRS0JnUURvZ1NHdE9qRjQwbFB3NTZJQ1xuOGg2TWtKZVZqWVhRTThlaEJwak1ua0ZsS1ZEYlkxMjBjaVNGRGdHaU0xazJwNnFMdFpyU05tRGZxOVNjRlIzcFxuNU5FL1FwbGVyd3JES3NvYzZpRldwSzVueG5uSzZCOHowMHQ2MDdnWTRSUENjeXExMG41WlBZbEtweE42ZDB1V1xuaDhwRVFwN3RGWWRvQkdZYy9icXNYSVlzWFFLQmdRQzFoeVIxZSttZXVZVXpIUkduS1FyaHdxZGtPQ2dmMEdxYVxuc2hnbG43cmZPci9UeWlORCszYXVhbncxZnBuMzA5RFlrQmg1cWFGUHZLQkI3VEhBdGk2SlBDc0ZxSFpxQzVHclxuL2sxcGFvLzBhQjlaM2d1TjhYeHk0RHlzWEQ1R2pzaE1LanRzRW4xSkQ5a3A4Y293M3FsOWRVUEJhUFZDSm5HMVxuQm9iVCtPcytLd0tCZ1FDQlpCdlJ3NmowakZpYW9NM1F4ZDJxYkcxdmxTcjdDMVgxank1SjhXaURXOUxieFJqSVxuNnh6WHowdXBjTm9kU0lIbzdsQVMzS0JjMmN1Z2NVQU1nb0xRcWNlZ29kbGpjOVMyOHJWSytxcjBwY2Z4Mit4QlxuY3oxMlJZMFdpMnZyc3h2NXhBTDh0dnBJeVdKVnJUNHJyN1lvOXNwck5xZjhnell3dkNPKytGN1RJUUtCZ0Q1NlxuRU5aT200MkJsSktQQXJCaHM5a1h3YjBBaHU3TU1LU2xmeUlUNDZGSSt4VE5rVzJvY3FSOUNkcnZnOWFFRkhFMFxueHZlNHBraG5SMURwYmlKQmthcXlCcXlmMm9HTkVjbjhjSEJEdU9BSnBpQ3NCNVlHOHlvbWV6dG5WQmU4dEx0aVxuSGFtSWc0NU40aFJKbjZsS09WTnd0SzB3anBrQjJralB3ai9hZ0R5WkFvR0FmKzBRdzl0QU56TnJoWFJ4bnNYbFxuZVBTMmRpTnV1bUlGVU5iTVZodHB2bncyWk12Zk1oNDRLdFNoQjlhZEpTNERaR2U3djNmSU0reStTTnhXMlVTUlxuVTVyS0trbWR5dmFzNm1YQ3JtRW9RNFQvUDJZeDl2NzdLaUxmQjRCRjFmV1QrYkMzaG9rYUJyL1F3dEtwaVJvelxuRks4SnBxSHBMSUdwQ3hJRkExbTg3M1U9XG4tLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tXG4iLCAiY2xpZW50X2VtYWlsIjogInRlc3RhY2Nlc3NAc3BlZWNoLWFwaS1wcm9qLmlhbS5nc2VydmljZWFjY291bnQuY29tIiwgImNsaWVudF9pZCI6ICIxMDIxMzU4MjI5OTIzOTY4MDg0MDAiLCAiYXV0aF91cmkiOiAiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tL28vb2F1dGgyL2F1dGgiLCAidG9rZW5fdXJpIjogImh0dHBzOi8vYWNjb3VudHMuZ29vZ2xlLmNvbS9vL29hdXRoMi90b2tlbiIsICJhdXRoX3Byb3ZpZGVyX3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vb2F1dGgyL3YxL2NlcnRzIiwgImNsaWVudF94NTA5X2NlcnRfdXJsIjogImh0dHBzOi8vd3d3Lmdvb2dsZWFwaXMuY29tL3JvYm90L3YxL21ldGFkYXRhL3g1MDkvdGVzdGFjY2VzcyU0MHNwZWVjaC1hcGktcHJvai5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSJ9").decode())
        credentials = service_account.Credentials.from_service_account_info(json_creds, scopes=SCOPES)

        # SENDING SOUND DATA TO SPEECH API
        client = speech.SpeechClient(credentials=credentials)
        response = client.recognize(
            config=speech.types.RecognitionConfig(
                encoding="FLAC",
                language_code="en-IN",
                # sample_rate_hertz=8000,
            ),
            # DEFAULT AUDIO FILE
            # "uri":"gs://cloud-samples-tests/speech/brooklyn.flac"

            audio=types.RecognitionAudio(content=decoded)
        )

        transcript = ""
        for result in response.results:
            transcript = result.alternatives[0].transcript

        # transcript = "name Surya BOOBOO " \
        #             "qualification MBBS " \
        #             "specialisation BBA " \
        #             "practice type public " \
        #             "email a l e v o o r s o o r y a 0 1 at the cost of gmail.com " \
        #             "area of practice New Delhi "
        #             "query I have stomach pain brah"

        # print("Sanity transcript check = ", transcript)
        mobile_number_string = str(json_data['mobile_number_string'])
        transcript_extracted_json_data = data_extractor(transcript, mobile_number_string)

        field_error_message = ""
        error_count = 0
        for k in transcript_extracted_json_data:
            if transcript_extracted_json_data[k]['value'] == None:
                field_error_message += transcript_extracted_json_data[k]['label'] + ", "
                error_count += 1

        if field_error_message == "" or (field_error_message != "" and error_count == 1 and (transcript_extracted_json_data['qualification']['value'] == "MBBS" and transcript_extracted_json_data['specialization']['value'] == None)):
            new_query = Query(name=transcript_extracted_json_data['name']['value'],
                              qualification=transcript_extracted_json_data['qualification']['value'],
                              qual_add_info=transcript_extracted_json_data['specialization']['value'],
                              practice_type=transcript_extracted_json_data['practice_type']['value'],
                              area_of_practice=transcript_extracted_json_data['area_of_practice']['value'],
                              mobile_no=transcript_extracted_json_data['mobile_number']['value'],
                              email=transcript_extracted_json_data['email']['value'],
                              query=transcript_extracted_json_data['query']['value'],
                              query_start_time=timezone.now()
                              )
            new_query.save()
            # CREATE STUFF FOR HTML_EMAIL
            subject = "You have a new query"
            html_content = '' \
                           '<p>You have a new Query #' + str(new_query.id) + '</p>'
            print(new_query.email)
            msg = EmailMessage(subject, html_content, to=[new_query.email])
            msg.content_subtype = "html"
            msg.send()
        else:
            # FORMAT ENGLISH OF ERROR MESSAGE ACCORDING TO NUMBER OF ERRORS

            # REMOVE LAST COMMA
            field_error_message = re.sub(r',\s$', '', field_error_message)

            # REPLACE LAST COMMA WITH 'AND'
            field_error_message = field_error_message.rsplit(',', 1)
            field_error_message = " and".join(field_error_message)

            field_error_message = "Your query could not be stored. " + field_error_message

            # CORRECT THE TENSE OF FIELD ERROR MESSAGE
            field_error_message += " were not provided" if error_count > 1 else " was not provided"

            # print(field_error_message)

        return JsonResponse(data=dict({"transcript":transcript_extracted_json_data, "sms_error_message": field_error_message}), status=200)
        # return HttpResponse(transcript, status=200)
    if request.method == "GET":
        return HttpResponse(status=404)
    return HttpResponse(status=500)

def login_view(request):
    return redirect(expert_view(request))


def logout_view(request):
    logout(request)
    return HttpResponseRedirect('/')
