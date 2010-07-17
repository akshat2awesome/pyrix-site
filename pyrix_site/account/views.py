# -*- coding: utf-8 -*-
from django import forms
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required

#from forms import SignatureForm

class SignatureForm(forms.Form):
    # name =  forms.CharField(label = 'Name', max_length=50)
    email = forms.EmailField(label = 'Email Address', help_text = 'Required')
    content = forms.CharField(widget = forms.widgets.Textarea(attrs = {
        'rows' : 4,
        'style' : 'width:100%;',
        'cols' : 20
        }),
        label = 'Comments', help_text = 'Optional', required = False
    )
  
    def clean_content(self):
      data = self.clean_data['content']
      if "http://" in data:
          raise forms.ValidationError("Cannot have HTML/Links in the comment")

      return data


def profile(request, user_id=None, template_name="account/profile.html"):
    view_user = request.user
    if user_id:
        view_user = get_object_or_404(User, pk = user_id)
    view_only = view_user != request.user
    ext_ctx = {'view_user':view_user, 'view_only':view_only }
    return render_to_response(template_name, ext_ctx, RequestContext(request))

@login_required
def signature(request, form_class=SignatureForm, template_name="account/signature.html"):
    profile = request.user.lbforum_profile
    if request.method == "POST":
        form = form_class(instance=profile, data=request.POST)
        form.save()
    else:
        form = form_class(instance=profile)
    ext_ctx = {'form': form}
    return render_to_response(template_name, ext_ctx, RequestContext(request))