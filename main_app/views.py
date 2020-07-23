from django.shortcuts import render, redirect
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.contrib.auth import login, authenticate, logout
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth.models import User, Group
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from django.core import serializers
from django.conf import settings

import pytz

from google.cloud import speech
from google.cloud.speech import types
from google.oauth2 import service_account

import math
import json
import base64
from io import BytesIO
import re
import hashlib, binascii
from dateutil.relativedelta import relativedelta

import time

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt

import numpy as np

from main_app.forms import QueryForm, ReplyForm, SetExpertForm, LocalhostLoginForm
from main_app.models import Query, Expert, Reply
from main_app.transcript_data_extractor import data_extractor


ITEMS_PER_PAGE = 10
ADMIN_EMAILS = settings.ADMIN_EMAILS

def index(request):
    queryForm = QueryForm()
    feedbackForm = ReplyForm()
    # localhostLoginForm = LocalhostLoginForm()
    context = {'queryForm': queryForm, 'feedbackForm': feedbackForm}
    # context = {'localhostLoginForm': localhostLoginForm}
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
            sendTo = SendTo()
            send_to_admin = sendTo.Admin()
            send_to_initiator = sendTo.Initiator()

            send_to_admin.new_query_notify(new_query)
            send_to_initiator.new_query_notify(new_query)

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

            # TO FETCH REPLIES FOR QUERIES UNDER 'THIS' EXPERT
            query_id_list = []
            for i in range(queries_list.count()):
                query_id_list.append(queries_list[i]['id'])
            replies = Reply.objects.filter(query__in=query_id_list)

            hashGen = HashGenerator()
            expert_hash_string = hashGen.hashstring_generator(str(expert.id)+expert.user.email)
            context = {'replyForm': replyForm, 'queries': queries, 'replies': replies,
                       'noOfPages': noOfPages, 'userHash': expert_hash_string}
            return render(request, 'expert.html', context)

        elif request.method == "POST":
            replyForm = ReplyForm(request.POST)
            if replyForm.is_valid():
                reply = replyForm.cleaned_data["reply"]
                reply_extra = replyForm.cleaned_data['reply_extra']
                queryId = replyForm.cleaned_data['queryId']

                new_reply = Reply(
                    reply=reply,
                    query=Query.objects.filter(id=queryId).get(),
                    expert=Expert.objects.filter(user=request.user).get(),
                    reply_extra=reply_extra,
                    reply_datetime=timezone.now(),
                )
                new_reply.save()

                if reply_extra == "" or reply_extra == None:
                    Query.objects.filter(id=queryId).update(needReply=False)
                    query = Query.objects.filter(id=queryId).get()
                    replies = Reply.objects.filter(query=query)

                    send_to = SendTo()
                    send_to.Admin().new_reply_notify(query, replies, False)
                    send_to.Initiator().new_reply_notify(query, replies, False)
                else:
                    Query.objects.filter(id=queryId).update(expert_assigned=None, needReply=True)
                    query = Query.objects.get(id=queryId)
                    replies = Reply.objects.filter(query=query)

                    send_to = SendTo()
                    send_to.Admin().new_reply_notify(query, replies, True)
                    send_to.Initiator().new_reply_notify(query, replies, True)

                return HttpResponse("Feedback sent")
            else:
                return JsonResponse(dict(replyForm.errors.items()))

    else:
        return HttpResponseRedirect('/logout/')


def set_expert_view(request):
    hashGen = HashGenerator()
    hash_string = hashGen.hashstring_generator("notExpert" + str(971368425))

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
                'userHash': hash_string,
                'noOfPagesExpertNotAssigned': noOfPagesExpertNotAssigned,
            }

            return render(request, "admin_pages/setExpert.html", context)

        else:
            replies = Reply.objects.filter().values('query', 'expert__user__first_name', 'expert__user__last_name',
                                                    'expert__user__username', 'reply', 'reply_extra', 'reply_datetime')
            experts = Expert.objects.all().order_by('user__groups__name')
            setExpertForm = SetExpertForm()

            context = None
            # print(pageNo, tabNo)
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
                    'userHash': hash_string,
                    'noOfPagesExpertNotAssigned': noOfPagesExpertNotAssigned,
                }

            if tabNo == "2":
                expertAssignedQueriesNeedReplyTrue = Query.objects.exclude(expert_assigned=None).filter(needReply=True) \
                    .values('id', 'name', 'qualification', 'qual_add_info', 'email', 'expert_assigned', 'query',
                            'needReply', 'query_start_time') \
                    .order_by('query_start_time')
                noOfPagesExpertAssignedNeedReplyTrue = int(
                    math.ceil(len(expertAssignedQueriesNeedReplyTrue) / ITEMS_PER_PAGE))
                paginator = Paginator(expertAssignedQueriesNeedReplyTrue, ITEMS_PER_PAGE)
                expertAssignedQueriesNeedReplyTrue = paginator.get_page(pageNo)

                context = {
                    'expertAssignedQueriesNeedReplyTrue': expertAssignedQueriesNeedReplyTrue,
                    'experts': experts, 'setExpertForm': setExpertForm, 'replies': replies,
                    'noOfPagesExpertAssignedNeedReplyTrue': noOfPagesExpertAssignedNeedReplyTrue,
                    'userHash': hash_string,
                    'tabNo:': tabNo
                }

            if tabNo == "3":
                expertAssignedQueriesNeedReplyFalse = Query.objects.exclude(expert_assigned=None).filter(needReply=False) \
                    .values('id', 'name', 'qualification', 'qual_add_info', 'email', 'expert_assigned', 'query',
                            'needReply', 'resolved', 'query_start_time') \
                    .order_by('query_start_time')
                noOfPagesExpertAssignedNeedReplyFalse = int(math.ceil(len(expertAssignedQueriesNeedReplyFalse) / ITEMS_PER_PAGE))
                paginator = Paginator(expertAssignedQueriesNeedReplyFalse, ITEMS_PER_PAGE)
                expertAssignedQueriesNeedReplyFalse = paginator.get_page(pageNo)

                context = {
                    'expertAssignedQueriesNeedReplyFalse': expertAssignedQueriesNeedReplyFalse,
                    'experts': experts, 'setExpertForm': setExpertForm, 'replies': replies,
                    'noOfPagesExpertAssigned': noOfPagesExpertAssignedNeedReplyFalse,
                    'userHash': hash_string,
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

                # GET THE GROUP NAME OF CHOSEN EXPERT
                expert_group = User.objects.filter(username=expert.user).values("groups")

                # FIND USERS WHO ARE IN THAT GROUP
                last_chosen_doc = User.objects.filter(groups__in=expert_group)

                # SET LAST_CHOSEN AS FALSE FOR THE LASTLY CHOSEN EXPERT
                Expert.objects.filter(user__in=last_chosen_doc, last_chosen=True).update(last_chosen=False)

                # SET LAST_CHOSEN AS TRUE FOR THE CURRENT EXPERT
                expert.last_chosen = True
                expert.save()
                Query.objects.filter(pk=queryId).update(expert_assigned=expert, needReply=True)

                # NOTIFY EXPERT
                sendToAdmin = SendTo().Admin()
                query = Query.objects.get(id=queryId)
                query.resolved = False
                query.save()
                replies = Reply.objects.filter(query=query)
                sendToAdmin.expert_set_notify(query, expert.user.email, replies)

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

            sendTo = SendTo()
            sendTo.Admin().new_query_notify(new_query)
            sendTo.Initiator().new_query_notify(new_query)
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


def process_reply_satisfaction(request, replyHash, queryId):
    query = Query.objects.get(id=queryId)
    if query.satisfaction_link_is_alive == False:
        data = "expired"
        return render(request, 'thankyouForFeedback.html', {'data': data})

    yes_data = (str(query.id) + str(query.name) + "yes").encode()
    no_data = (str(query.id) + str(query.name) + "no").encode()

    yes_link_hash = hashlib.pbkdf2_hmac('sha256', yes_data, b"satisfaction", 100000)
    yes_link_hash_string = binascii.hexlify(yes_link_hash).decode()

    no_link_hash = hashlib.pbkdf2_hmac('sha256', no_data, b"satisfaction", 100000)
    no_link_hash_string = binascii.hexlify(no_link_hash).decode()

    data = "no"
    if replyHash == yes_link_hash_string:
        data = "yes"
        query.resolved=True
    elif replyHash == no_link_hash_string:
        data = "no"
        print("In No link hash string")
        sendTo = SendTo.Admin()
        sendTo.not_satisfied_notify(query)

    query.satisfaction_link_is_alive = False
    query.save()
    return render(request, 'thankyouForFeedback.html', {'data': data})


def search_query(request):
    # querySerializer()
    queryId = request.GET['searchQueryId']

    hashGen = HashGenerator()

    # DEFAULT IS BLANK IF THERE IS NO userHash, userHash IS SET FOR VALID EXPERTS AND ADMIN
    userHash = request.GET.get('userHash', "")
    expertHash = "" # DEFAULT

    if not request.user.is_anonymous:
        expert = Expert.objects.get(user=request.user)
        expertHash = hashGen.hashstring_generator(str(expert.id) + expert.user.email)

    # CREATE ADMIN HASH TO CHECK IF USER IS ADMIN OR NOT
    adminHash = hashGen.hashstring_generator("notExpert" + str(971368425))

    try:
        searchQuery = Query.objects.get(id=queryId)
        if userHash == expertHash:
            expert = Expert.objects.get(user=request.user)
            searchQuery = Query.objects.get(id=queryId, expert_assigned=expert, needReply=True)

        elif userHash != adminHash and userHash == "":
            print("Unauthentic user")
            # do 404 error

        searchReplies = Reply.objects.filter(query=searchQuery).values('query', 'expert__user__first_name',
                                                                       'expert__user__last_name',
                                                                       'expert__user__username', 'reply',
                                                                       'reply_extra', 'reply_datetime')

        # SET CONTEXT ACCORDING TO THE TYPE OF USER
        if userHash == adminHash:
            experts = Expert.objects.all().order_by('user__groups__name')
            context = {
                "searchQuery": searchQuery,
                "experts": experts,
                "searchReplies": searchReplies,
            }
            return render(request, 'admin_pages/adminSearchResultQuery.html', context)
        else:
            replyForm = ReplyForm()

            context = {
                "searchQuery": searchQuery,
                "searchReplies": searchReplies,
                "replyForm": replyForm,
            }
            return render(request, 'expertSearchResultQuery.html', context)

    except ObjectDoesNotExist:
        return JsonResponse({"error": "error"}, status=500)


def login_view(request):
    return redirect(expert_view(request))


def logout_view(request):
    logout(request)
    return HttpResponseRedirect('/')


def generate_report(request):

    if request.method == "GET":
        report_type = request.GET.get("report_type")
        from_date = request.GET.get("custom_from")
        to_date = request.GET.get("custom_to")

        local_timezone = pytz.timezone('Asia/Kolkata')
        if from_date is not None and to_date is not None:
            from_date = timezone.datetime.strptime(from_date, "%d-%m-%Y")
            from_date = from_date.astimezone(timezone.utc)

            to_date = timezone.datetime.strptime(to_date, "%d-%m-%Y")
            to_date = to_date.replace(hour=timezone.now().astimezone(local_timezone).hour,
                                  minute=timezone.now().astimezone(local_timezone).minute,
                                  second=timezone.now().astimezone(local_timezone).second)
            to_date = to_date.astimezone(timezone.utc)

            if from_date > to_date:
                temp_date = to_date
                to_date = from_date
                from_date = temp_date
        else:
            from_date = None
            to_date = None

        if report_type != "" and report_type != None:
            report_type = int(report_type)

            graph_generator = Graph_Generator()
            svg1, timeStr = graph_generator.public_private_count(report_type, from_date, to_date)
            svg2 = graph_generator.district_wise(report_type, from_date, to_date)
            svg3 = graph_generator.experts_consulted(report_type, from_date, to_date)
            svg4 = graph_generator.provider_qualification(report_type, from_date, to_date)
            svg5 = graph_generator.reply_times(report_type, from_date, to_date)
            # print("Title = ", timeStr)
            context = {"public_private_count_graph": svg1, "timeStr": timeStr,
                       "district_wise_practitioner_dist_graph": svg2,
                       "experts_consulted_graph": svg3,
                       "provider_qualification_graph": svg4,
                       "reply_time_graph": svg5}
            return render(request, 'graph_page/graph_elements.html', context)
        else:
            # print("Empty hai re")
            return render(request, 'graph_page/graph_elements.html')


class HashGenerator:
    def hashstring_generator(self, data):
        if type(data) is not bytes:
            data = data.encode()
        link_hash = hashlib.pbkdf2_hmac('sha256', data, b"satisfaction", 100000)
        hash_string = binascii.hexlify(link_hash).decode()

        return hash_string


class SendTo:
    class Admin:
        def new_query_notify(self, query):
            # FOR ADMINS
            html_content = render_to_string('email/admin/post_query_submit_email.html', {"query": query})
            msg = EmailMultiAlternatives(
                subject="New Query #" + str(query.id) + " received",
                to=ADMIN_EMAILS
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()

        def not_satisfied_notify(self, query):
            print(query)
            print("In not_satisfied")
            # FOR QUERY INITIATOR
            html_content = render_to_string('email/admin/not_satisfied_email.html', {"query": query})
            msg = EmailMultiAlternatives(
                subject="[NEED ACTION] Response for Query #" + str(query.id) + " has been marked as unsatisfactory by "+str(query.name),
                to=ADMIN_EMAILS
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            print("sent email to Admins")

        def new_reply_notify(self, query, replies, needAction):
            if needAction:
                html_content = render_to_string('email/admin/new_reply_2_admin_notify_email.html',
                                                {"query": query, "replies": replies})
                msg = EmailMultiAlternatives(
                    subject="[NEED ACTION] Reply received for Query #" + str(query.id),
                    to=ADMIN_EMAILS
                )
            else:
                html_content = render_to_string('email/admin/new_reply_1_admin_notify_email.html',
                                                {"query": query, "replies": replies})

                msg = EmailMultiAlternatives(
                    subject="[NEW REPLY] Reply received for Query #" + str(query.id),
                    to=ADMIN_EMAILS
                )
            msg.attach_alternative(html_content, "text/html")
            msg.send()

        def expert_set_notify(self, query, email, replies):
            # FOR QUERY INITIATOR
            html_content = render_to_string('email/admin/expert_set_notify_email.html',
                                            {"query": query,
                                             "replies": replies})
            msg = EmailMultiAlternatives(
                subject="You Have a New Query #" + str(query.id),
                to=[email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()

    class Initiator:
        def new_query_notify(self, query):
            # FOR QUERY INITIATOR
            html_content = render_to_string('email/query_initiator/post_query_submit_email.html', {"query": query})
            msg = EmailMultiAlternatives(
                subject="Your Query #" + str(query.id) + " has been received",
                to=[query.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()

        def new_reply_notify(self, query, replies, needs_2nd_opinion):

            if needs_2nd_opinion:
                html_content = render_to_string('email/query_initiator/new_reply_2_email.html',
                                                {"query": query, "replies": replies})
            else:
                yes_link_data = (str(query.id)+str(query.name)+"yes").encode()
                no_link_data = (str(query.id) + str(query.name) + "no").encode()
                linkGenerator = HashGenerator()
                yes_link_hashstring = linkGenerator.hashstring_generator(yes_link_data)
                no_link_hashstring = linkGenerator.hashstring_generator(no_link_data)
                query.satisfaction_link_is_alive = True
                query.save()

                html_content = render_to_string('email/query_initiator/new_reply_1_email.html',
                                                {"query": query, "replies": replies,
                                                 "queryId": query.id,
                                                 "yes_hash_string": yes_link_hashstring,
                                                 "no_hash_string": no_link_hashstring})
            msg = EmailMultiAlternatives(
                subject="[NEW REPLY] Your Query #" + str(query.id) + " has a new reply",
                to=[query.email]
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()


def querySerializer(request):
    data = Query.objects.all().order_by("query_start_time").values()
    data_list = list(data)
    return JsonResponse(data_list, safe=False)


class Graph_Generator:

    DAILY = 1
    WEEKLY = 7
    MONTHLY = 1
    local_timezone = pytz.timezone('Asia/Kolkata')
    from_time = timezone.now().astimezone(local_timezone).replace(hour=0, minute=0, second=0, microsecond=0)
    timeStr = ""
    print("TIME = ", (from_time - relativedelta(days=1)).strftime("%d %B %I:%M%p"), "-",
          timezone.now().astimezone(local_timezone).strftime("%d %B %I:%M%p"))


    def public_private_count(self, report_type=1, from_date=None, to_date=None):
        if report_type == 1:
            public_count = Query.objects.filter(practice_type=1,
                                                query_start_time__gte=timezone.now() - relativedelta(days=Graph_Generator.DAILY)).count()
            private_count = Query.objects.filter(query_start_time__gte=timezone.now() - relativedelta(days=Graph_Generator.DAILY)).count() - public_count

            timeStr = (Graph_Generator.from_time - relativedelta(days=Graph_Generator.DAILY)).strftime("%d %B %Y %I:%M%p") + \
                      " - " + timezone.now().astimezone(Graph_Generator.local_timezone).strftime("%d %B %Y %I:%M%p")
            # print(timeStr)

        elif report_type == 2:
            public_count = Query.objects.filter(practice_type=1,
                                                query_start_time__gte=timezone.now() - relativedelta(days=Graph_Generator.WEEKLY)).count()
            private_count = Query.objects.filter(query_start_time__gte=timezone.now() - relativedelta(days=Graph_Generator.WEEKLY)).count() - public_count

            timeStr = (Graph_Generator.from_time - relativedelta(days=Graph_Generator.WEEKLY)).strftime(
                "%d %B %Y %I:%M%p") + \
                      " - " + timezone.now().astimezone(Graph_Generator.local_timezone).strftime("%d %B %Y %I:%M%p")
            # print(timeStr)

        elif report_type == 3:
            public_count = Query.objects.filter(practice_type=1,
                                                query_start_time__gte=timezone.now() - relativedelta(months=Graph_Generator.MONTHLY)).count()
            private_count = Query.objects.filter(
                query_start_time__gte=timezone.now() - relativedelta(months=Graph_Generator.MONTHLY)).count() - public_count

            timeStr = (Graph_Generator.from_time - relativedelta(months=Graph_Generator.MONTHLY)).strftime(
                "%d %B %Y %I:%M%p") + \
                      " - " + timezone.now().astimezone(Graph_Generator.local_timezone).strftime("%d %B %Y %I:%M%p")
            # print(timeStr)

        elif report_type == 5:
            public_count = Query.objects.filter(practice_type=1, query_start_time__gte=from_date, query_start_time__lte=to_date).count()
            private_count = Query.objects.filter(query_start_time__gte=from_date, query_start_time__lte=to_date).count() - public_count

            timeStr = (from_date.astimezone(Graph_Generator.local_timezone).replace(hour=0, minute=0).strftime("%d %B %Y %I:%M%p")) + \
                      " - " + to_date.astimezone(Graph_Generator.local_timezone).strftime("%d %B %I:%M%p")
            # print(timeStr)
        else:
            public_count = Query.objects.filter(practice_type=1).count()
            private_count = Query.objects.count() - public_count

            timeStr = "Overall"

        x_labels = ['Public', 'Private']
        bar_width = 0.4
        index = np.arange(2)
        fig = plt.figure()
        bars = plt.bar(index, [public_count, private_count], width=bar_width)
        plt.xticks(index, x_labels, fontsize=10)
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, 1.00005*bar.get_height(),
                     '%d'%int(height), ha='center', va='bottom')
        plt.xlabel("Practitioner type")
        plt.ylabel("Number of practitioners raising queries")
        plt.title("Practitioner graph")
        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='svg')
        svg1_HTML = '<svg' + str(buffer.getvalue()).split('<svg')[1].replace('\\n', '').replace('\\r', '')[:-1]
        # buffer.close()
        plt.close()

        return svg1_HTML, timeStr

    def district_wise(self, report_type=1, from_date=None, to_date=None):
        if report_type == 1:

            districts = Query.objects.filter(query_start_time__gte=timezone.now() - relativedelta(days=Graph_Generator.DAILY))\
                .order_by("area_of_practice").values("area_of_practice") \
                .annotate(Count('area_of_practice'))

        elif report_type == 2:
            districts = Query.objects.filter(query_start_time__gte=timezone.now() - relativedelta(days=Graph_Generator.WEEKLY))\
                .order_by("area_of_practice").values("area_of_practice") \
                .annotate(Count('area_of_practice'))

        elif report_type == 3:
            districts = Query.objects.filter(
                query_start_time__gte=timezone.now() - relativedelta(months=Graph_Generator.MONTHLY)) \
                .order_by("area_of_practice").values("area_of_practice") \
                .annotate(Count('area_of_practice'))
        elif report_type == 5:
            districts = Query.objects.filter(
                query_start_time__gte=from_date, query_start_time__lte=to_date) \
                .order_by("area_of_practice").values("area_of_practice") \
                .annotate(Count('area_of_practice'))
        else:
            print("IN ELSE")
            districts = Query.objects.order_by("area_of_practice").values("area_of_practice")\
            .annotate(Count('area_of_practice'))

        x_labels = []
        y_vals = []
        bar_width = 0.4
        index = np.arange(districts.count())
        fig = plt.figure()

        for district in districts:
            x_labels.append(district["area_of_practice"])
            y_vals.append(district['area_of_practice__count'])

        bars = plt.bar(index, y_vals, width=bar_width)
        plt.xticks(index, x_labels, rotation=20, fontsize=10)

        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, 1.00005 * bar.get_height(),
                     '%d' % int(height), ha='center', va='bottom')

        plt.xlabel("District Names")
        plt.ylabel("Number of practitioners raising queries")
        plt.title("District-wise Practitioner distribution")
        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='svg')
        svg2_HTML = '<svg' + str(buffer.getvalue()).split('<svg')[1].replace('\\n', '').replace('\\r', '')[:-1]
        # buffer.close()
        plt.close()
        return svg2_HTML

    def experts_consulted(self, report_type=1, from_date=None, to_date=None):
        if report_type == 1:
            expert_groups = Reply.objects.filter(reply_datetime__gte = timezone.now() - relativedelta(days=Graph_Generator.DAILY)).order_by("expert__user__groups").values("expert__user__groups__name") \
                .annotate(Count('expert__user__groups'))
        elif report_type == 2:
            expert_groups = Reply.objects.filter(reply_datetime__gte = timezone.now() - relativedelta(days=Graph_Generator.WEEKLY)).order_by(
                "expert__user__groups").values("expert__user__groups__name") \
                .annotate(Count('expert__user__groups'))
        elif report_type == 3:
            expert_groups = Reply.objects.filter(reply_datetime__gte = timezone.now() - relativedelta(months=Graph_Generator.MONTHLY)).order_by(
                "expert__user__groups").values("expert__user__groups__name") \
                .annotate(Count('expert__user__groups'))
        elif report_type == 5:
            expert_groups = Reply.objects.filter(
                reply_datetime__gte=from_date, reply_datetime__lte=to_date).order_by(
                "expert__user__groups").values("expert__user__groups__name") \
                .annotate(Count('expert__user__groups'))
        else:
            expert_groups = Reply.objects.order_by(
                "expert__user__groups").values("expert__user__groups__name") \
                .annotate(Count('expert__user__groups'))

        x_labels = []
        y_vals = []
        bar_width = 0.4
        index = np.arange(expert_groups.count())
        fig = plt.figure()

        for expert_group in expert_groups:
            x_labels.append(expert_group["expert__user__groups__name"])
            y_vals.append(expert_group['expert__user__groups__count'])

        bars = plt.bar(index, y_vals, width=bar_width)
        plt.xticks(index, x_labels, rotation=20, fontsize=10)

        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, 1.00005 * bar.get_height(),
                     '%d' % int(height), ha='center', va='bottom')

        plt.xlabel("Expert Type")
        plt.ylabel("Number of times Experts were Consulted")
        plt.title("Expert Type-wise Consultation Distribution")
        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='svg')
        svg3_HTML = '<svg' + str(buffer.getvalue()).split('<svg')[1].replace('\\n', '').replace('\\r', '')[:-1]
        # buffer.close()
        plt.close()
        return svg3_HTML

    def provider_qualification(self, report_type=1, from_date=None, to_date=None):
        if report_type == 1:
            provider_qualifications = Query.objects.filter(query_start_time__gte=timezone.now() - relativedelta(days=Graph_Generator.DAILY))\
                .order_by("qualification").values("qualification", "qual_add_info") \
                .annotate(Count('qualification'))

        elif report_type == 2:
            provider_qualifications = Query.objects.filter(
                query_start_time__gte=timezone.now() - relativedelta(days=Graph_Generator.WEEKLY)) \
                .order_by("qualification").values("qualification", "qual_add_info") \
                .annotate(Count('qualification'))

        elif report_type == 3:
            provider_qualifications = Query.objects.filter(
                query_start_time__gte=timezone.now() - relativedelta(months=Graph_Generator.MONTHLY)) \
                .order_by("qualification").values("qualification", "qual_add_info") \
                .annotate(Count('qualification'))
        elif report_type == 5:
            provider_qualifications = Query.objects.filter(
                query_start_time__gte=from_date, query_start_time__lte=to_date) \
                .order_by("qualification").values("qualification", "qual_add_info") \
                .annotate(Count('qualification'))
        else:
            provider_qualifications = Query.objects.order_by("qualification").values("qualification", "qual_add_info") \
                .annotate(Count('qualification'))

        x_labels = []
        y_vals = []
        bar_width = 0.4
        index = np.arange(provider_qualifications.count())
        fig = plt.figure()

        for qualification in provider_qualifications:
            main_info = ""
            addn_info = ""
            qualInfo = qualification["qualification"]

            if qualInfo != "MBBS":
                if qualInfo == "OTR":
                    main_info = "Other"
                if qualInfo == "SPC":
                    main_info = "Specialist"

                addn_info = "("+qualification["qual_add_info"]+")"

            elif qualInfo == "MBBS":
                main_info = "MBBS"

            else:
                main_info = "Unknown"

            x_label_val = str(main_info)+"\n"+str(addn_info)
            x_labels.append(x_label_val)
            y_vals.append(qualification['qualification__count'])

        bars = plt.bar(index, y_vals, width=bar_width)
        plt.xticks(index, x_labels, rotation=20, fontsize=10)

        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, 1.00005 * bar.get_height(),
                     '%d' % int(height), ha='center', va='bottom')

        plt.xlabel("Provider Qualification")
        plt.ylabel("Number of Query Providers")
        plt.title("Provider Qualification Distribution")
        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='svg')
        svg4_HTML = '<svg' + str(buffer.getvalue()).split('<svg')[1].replace('\\n', '').replace('\\r', '')[:-1]
        # buffer.close()
        plt.close()
        return svg4_HTML

    def reply_times(self, report_type=1, from_date=None, to_date=None):
        if report_type == 1:
            replyTimes = Reply.objects.filter(
                reply_datetime__gte=timezone.now() - relativedelta(days=Graph_Generator.DAILY))\
                .order_by("query", "reply_datetime") \
                .values("reply_datetime", "query", "query__query_start_time")
        elif report_type == 2:
            replyTimes = Reply.objects.filter(
                reply_datetime__gte=timezone.now() - relativedelta(days=Graph_Generator.WEEKLY)).order_by(
                "query", "reply_datetime") \
                .values("reply_datetime", "query", "query__query_start_time")
        elif report_type == 3:
            replyTimes = Reply.objects.filter(
                reply_datetime__gte=timezone.now() - relativedelta(months=Graph_Generator.MONTHLY)).order_by(
                "query", "reply_datetime") \
                .values("reply_datetime", "query", "query__query_start_time")
        elif report_type == 5:
            replyTimes = Reply.objects.filter(
                reply_datetime__gte=from_date, reply_datetime__lte=to_date).order_by(
                "query", "reply_datetime") \
                .values("reply_datetime", "query", "query__query_start_time")
        else:
            replyTimes = Reply.objects.order_by("query", "reply_datetime")\
                .values("reply_datetime", "query", "query__query_start_time")

        index = np.arange(5)
        bar_width = 0.4
        fig = plt.figure()
        times = [0, 0, 0, 0, 0] # FOR STORING COUNT OF REPLIES GIVEN UNDER CERTAIN TIME INTERVALS

        i = 0
        for replyTime in replyTimes:
            # print("\n", replyTime['query'], "\n", replyTime['query__query_start_time'], "\n", replyTime['reply_datetime'], )
            if i == 0:
                queryNo0 = replyTime['query']
                replyTime0 = replyTime['query__query_start_time']

            if queryNo0 == replyTime['query']:
                i = 1
                # print("isEqual")
                reply_time_seconds = (replyTime['reply_datetime'] - replyTime0).seconds
                reply_time_days = (replyTime['reply_datetime'] - replyTime0).days
                hours = reply_time_seconds/(60*60)

                if reply_time_days > 0:
                    times[4] += 1
                else:
                    temp = hours/6
                    if temp <= 1:
                        times[0] += 1
                    elif temp > 1 and temp <= 2:
                        times[1] += 1
                    elif temp > 2 and temp <= 3:
                        times[2] += 1
                    elif temp >3 and temp <= 4:
                        times[3] += 1
            else:
                # print("\nin else")
                reply_time_seconds = (replyTime['reply_datetime'] - replyTime['query__query_start_time']).seconds
                reply_time_days = (replyTime['reply_datetime'] - replyTime['query__query_start_time']).days
                hours = reply_time_seconds / (60 * 60)

                if reply_time_days > 0:
                    times[4] += 1
                else:
                    temp = hours / 6
                    if temp <= 1:
                        times[0] += 1
                    elif temp > 1 and temp <= 2:
                        times[1] += 1
                    elif temp > 2 and temp <= 3:
                        times[2] += 1
                    elif temp > 3 and temp <= 4:
                        times[3] += 1


            replyTime0 = replyTime['reply_datetime']
            queryNo0 = replyTime['query']

        x_labels = ["<=6 Hours", ">6 and <=12 Hours", ">12 and <=18 Hours", ">18 and <=24 hours", ">24 hours"]
        y_vals = times

        bars = plt.bar(index, y_vals, width=bar_width)
        plt.xticks(index, x_labels, rotation=20, fontsize=10)

        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width() / 2, 1.00005 * bar.get_height(),
                     '%d' % int(height), ha='center', va='bottom')

        plt.xlabel("Hours taken to reply")
        plt.ylabel("Number of Replies")
        plt.title("Time Table for Replies")
        plt.tight_layout()

        buffer = BytesIO()
        fig.savefig(buffer, format='svg')
        svg5_HTML = '<svg' + str(buffer.getvalue()).split('<svg')[1].replace('\\n', '').replace('\\r', '')[:-1]
        buffer.close()
        plt.close()

        return svg5_HTML

