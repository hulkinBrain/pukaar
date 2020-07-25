from django import forms
from django.forms import ModelForm, Textarea, CharField, TextInput
from django.core.exceptions import ValidationError
from main_app.models import Query
from main_app.choices import *


class LocalhostLoginForm(forms.Form):
    email = forms.EmailField(label="Email:")
    password = forms.CharField(widget=forms.PasswordInput())

class QueryForm(ModelForm):
    practice_type = forms.ChoiceField(widget=forms.RadioSelect, choices=PRACTICE_TYPE_CHOICE)
    class Meta:
        model = Query
        exclude = ['query_start_time', 'expert_assigned', 'reply', 'reply_extra', 'previous_experts', 'resolved',
                   'needReply', 'final_reply_receive_time', 'satisfaction', 'satisfaction_link_is_alive']
        labels = {
            'qual_add_info': 'Expertise'
        }
        widgets = {
            'area_of_practice': Textarea(attrs={'class': 'materialize-textarea', 'placeholder': 'Delhi'}),
            'qual_add_info': TextInput(attrs={'disabled': ''}),
            'mobile_no': TextInput(attrs={'placeholder': '9876543210'}),
            'query': Textarea(attrs={'class': 'materialize-textarea'}),
        }
    def clean(self):
        if self.cleaned_data.get('qualification') != "MBBS" and self.cleaned_data.get('qual_add_info') == None:
            self.add_error('qual_add_info', 'This field is required')
            # raise ValidationError("Fill additional details field")
        return self.cleaned_data


class ReplyForm(forms.Form):
    queryId = forms.IntegerField(widget=forms.HiddenInput())
    reply = forms.CharField(label="Reply", widget=forms.Textarea(attrs={
        'class': 'materialize-textarea',
        'placeholder': 'Enter reply here',
    }))
    reply_extra = forms.CharField(required=False, label='Extra Comments (optional)',
                                  widget=forms.Textarea(attrs={
                                      'class': 'materialize-textarea',
                                      'placeholder': 'To refer to another expert, enter information here'
                                  }))



class SetExpertForm(forms.Form):
    queryId = forms.IntegerField(widget=forms.HiddenInput())
    expertId = forms.IntegerField(widget=forms.HiddenInput())