from django.db import models
from main_app.choices import *
from django.core.validators import RegexValidator
from datetime import datetime
from django.contrib.auth.models import User
# Create your models here.

# FOR EXPERTS
class Expert(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    mobile_regex = RegexValidator(regex=r'^\+\d{12}$')
    mobile_no = models.CharField(validators=[mobile_regex], max_length=13, blank=True, null=True)
    last_chosen = models.BooleanField(default=False, null=False)


# FOR NORMAL DOCTORS
class Query(models.Model):
    name = models.CharField(max_length=50, default='', blank=False, null=False)
    qualification = models.CharField(max_length=4, choices=QUALIFICATION_CHOICE, blank=False, null=False, default=1)
    qual_add_info = models.CharField(max_length=50, blank=True, default=None, null=True)
    practice_type = models.IntegerField(default=1, choices=PRACTICE_TYPE_CHOICE, blank=False, null=False)
    area_of_practice = models.TextField(max_length=100, blank=False, null=False)
    mobile_regex = RegexValidator(regex=r'^\d{10}$')
    mobile_no = models.CharField(validators=[mobile_regex], max_length=13, blank=False, null=False)
    email = models.EmailField(blank=False, null=False)
    query = models.TextField(blank=False, null=False)
    query_start_time = models.DateTimeField(blank=True, null=False)
    expert_assigned = models.ForeignKey(Expert, on_delete=models.CASCADE, default=None, null=True)
    needReply = models.BooleanField(default=True, null=False, blank=True)
    resolved = models.BooleanField(default=False, null=False, blank=True)
    satisfaction_link_is_alive = models.BooleanField(default=False, null=False, blank=True)
    satisfaction = models.IntegerField(choices=SATISFACTION_CHOICE, null=True, blank=True)


class Reply(models.Model):
    query = models.ForeignKey(Query, on_delete=models.CASCADE, default=None, null=True)
    expert = models.ForeignKey(Expert, on_delete=models.CASCADE, default=None, null=True)
    reply = models.TextField(blank=False, null=False)
    reply_extra = models.TextField(blank=True, null=True, default=None)
    reply_datetime = models.DateTimeField(blank=True, null=True)