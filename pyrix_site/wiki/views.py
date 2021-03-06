# -*- coding: utf-8 -*-
import difflib

from django.http import Http404
from django.http import HttpResponseRedirect
from django.http import HttpResponseBadRequest
from django.http import HttpResponseNotFound
from django.http import HttpResponseForbidden
from django.shortcuts import render_to_response
from django.shortcuts import get_object_or_404
from django.template.context import RequestContext
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.core.exceptions import ObjectDoesNotExist

from wiki.forms import *
from wiki.models import *
from wiki.settings import *


__all__ = [
    'index',
    'page',
    'edit',
    'revisions',
    'changes',
    'revision_list',
    'page_list',
]


def index(request, template_name='wiki/wiki_page.html'):
    """Redirects to the default wiki index name.

    It's the base view function to redirect to wiki pages. When the browser 
    request the wiki root, the urls will call the index function. If there is a
    group in request, the views.index function will redirect to wiki_page which
    will call the views.page function.
    """

    kwargs = {
        'slug': DEFAULT_INDEX,
    }

    # be group aware
    #group = getattr(request, "group", None)

    #if group:
    #    redirect_to = request.bridge.reverse('wiki_page', group, kwargs=kwargs)
    #else:
    #    redirect_to = reverse('wiki_page', kwargs=kwargs)
    redirect_to = reverse('wiki_page', kwargs=kwargs)
    return HttpResponseRedirect(redirect_to)


def page(request, slug, rev_id=None, template_name='wiki/wiki_page.html',
    extra_context=None):
    """Displays a wiki page. Redirects to the edit view if the page doesn't
    exist.
    
    Show the pages.
    """
    
    if extra_context is None:
        extra_context = {}

    # be group aware
    #group = getattr(request, "group", None)
    
    #if group:
    #    bridge = request.bridge
    #    group_base = bridge.group_base_template()
    #else:
    #    bridge = None
    #    group_base = None

    #try:
    #    if group:
    #        queryset = group.content_objects(WikiPage)
    #    else:
    #        queryset = WikiPage.objects.all()
    try:
        page = WikiPage.objects.get(slug=slug)
        rev = page.current
    
        if rev_id:
            rev_spec = Revision.object.get(pk=rev_id)
            if rev.pk != rev_spec.pk:
                rev_spec.is_not_current = True
            rev = rev_spec
        #page = queryset.get(slug=slug)
        #rev = page.current

        # Display an older revision if rev_id is given
        #if rev_id:
        #    if group:
        #        revision_queryset = group.content_objects(Revision, join="page")
        #    else:
        #        revision_queryset = Revision.objects.all()
        #    rev_specific = revision_queryset.get(pk=rev_id)
        #    if rev.pk != rev_specific.pk:
        #        rev_specific.is_not_current = True
        #    rev = rev_specific

    # The Page does not exist, redirect to the edit form or
    # deny, if the user has no permission to add pages
    except WikiPage.DoesNotExist:
        if request.user.is_authenticated():
            kwargs = {
                'slug': slug,
            }
            #if group:
            #    redirect_to = bridge.reverse('wiki_edit', group, kwargs=kwargs)
            #else:
            #    redirect_to = reverse('wiki_edit', kwargs=kwargs)
            redirect_to = reverse('wiki_edit', kwargs=kwargs)
            return HttpResponseRedirect(redirect_to)
        else:
            raise Http404
    template_context = {
        'page': page,
        'rev': rev,
        #'group': group,
        #'group_base': group_base,
    }
    template_context.update(extra_context)
    return render_to_response(template_name, template_context,
        RequestContext(request))


def edit(request, slug, rev_id=None, template_name='wiki/wiki_edit.html',
         extra_context=None, wiki_page_form=WikiPageForm,
         wiki_delete_form=DeleteWikiPageForm):
    """Displays the form for editing and deleting a page.
    
    The wiki's edit interface.
    """
    
    if extra_context is None:
        extra_context = {}

    # be group aware
    #group = getattr(request, "group", None)
    #if group:
    #    bridge = request.bridge
    #    group_base = bridge.group_base_template()
    #else:
    #    bridge = None
    #    group_base = None

    # Get the page for slug and get a specific revision, if given
    try:
        #if group:
        #    queryset = group.content_objects(WikiPage)
        #else:
        #    queryset = WikiPage.objects.all()
        page = WikiPage.objects.get(slug=slug)
        rev = page.current
        initial = {
            'content': page.current.content,
        }

        # Do not allow editing wiki pages if the user has no permission
        if not request.user.has_perms(('wiki.change_wikipage', 'wiki.change_revision' )):
            return HttpResponseForbidden(_(u"You don't have permission to edit pages."))

        if rev_id:
            # There is a specific revision, fetch this
            rev_specific = Revision.objects.get(pk=rev_id)
            if rev.pk != rev_specific.pk:
                rev = rev_specific
                rev.is_not_current = True
                initial = {
                    'content': rev.content, 
                    'message': _(u'Reverted to "%s"' % rev.message),
                }


    # This page does not exist, create a dummy page
    # Note that it's not saved here
    except WikiPage.DoesNotExist:

        # Do not allow adding wiki pages if the user has no permission
        if not request.user.has_perms(('wiki.add_wikipage', 'wiki.add_revision',)):
            return HttpResponseForbidden(_(u"You don\'t have permission to add wiki pages."))

        page = WikiPage(slug=slug)
        page.is_initial = True
        rev = None
        initial = {
            'content': _('Describe your new page %s here...' % slug),
            'message': _('Initial revision'),
        }

    # Don't display the delete form if the user has nor permission
    delete_form = None
    # The user has permission, then do
    if request.user.has_perm('wiki.delete_wikipage') or request.user.has_perm('wiki.delete_revision'):
        delete_form = wiki_delete_form(request)
        if request.method == 'POST' and request.POST.get('delete'):
            delete_form = wiki_delete_form(request, request.POST)
            if delete_form.is_valid():
                return delete_form.delete_wiki(request, page, rev)

    # Page add/edit form
    form = wiki_page_form(initial=initial)
    if request.method == 'POST':
        form = wiki_page_form(data=request.POST)
        if form.is_valid():
            # Check if the content is changed, except there is a rev_id and the
            # user possibly only reverted the HEAD to it
            if not rev_id and initial['content'] == form.cleaned_data['content']:
                form.errors['content'] = (_(u'You have made no changes!'),)

            # Save the form and redirect to the page view
            else:
                try:
                    # Check that the page already exist
                    #if group:
                    #    queryset = group.content_objects(WikiPage)
                    #else:
                    #    queryset = WikiPage.objects.all()
                    page = WikiPage.objects.get(slug=slug)
                except WikiPage.DoesNotExist:
                    # Must be a new one, create that page
                    page = WikiPage(slug=slug)
                    #if group:
                    #    page = group.associate(page, commit=False)
                    page.save()

                form.save(request, page)

                kwargs = {
                    'slug': page.slug,
                }

                #if group:
                #    redirect_to = bridge.reverse('wiki_page', group, kwargs=kwargs)
                #else:
                #    redirect_to = reverse('wiki_page', kwargs=kwargs)
                
                redirect_to = reverse('wiki_page', kwargs=kwargs)
                request.user.message_set.create(message=_(u'Your changes to %s were saved' % page.slug))
                return HttpResponseRedirect(redirect_to)

    template_context = {
        'form': form,
        'delete_form': delete_form,
        'page': page,
        'rev': rev,
        #'group': group,
        #'group_base': group_base,
    }
    template_context.update(extra_context)
    return render_to_response(template_name, template_context,
        RequestContext(request))


def revisions(request, slug, template_name='wiki/wiki_revisions.html', extra_context=None):
    """Displays the list of all revisions for a specific WikiPage.
    
    """
    
    if extra_context is None:
        extra_context = {}

    # be group aware
    #group = getattr(request, "group", None)
    #if group:
    #    bridge = request.bridge
    #    group_base = bridge.group_base_template()
    #else:
    #    bridge = None
    #    group_base = None

    #if group:
    #    queryset = group.content_objects(WikiPage)
    #else:
    #    queryset = WikiPage.objects.all()
    page = get_object_or_404(WikiPage.objects.all(), slug=slug)

    template_context = {
        'page': page,
        #'group': group,
        #'group_base': group_base,
    }
    template_context.update(extra_context)
    return render_to_response(template_name, template_context,
        RequestContext(request))


def changes(request, slug, template_name='wiki/wiki_changes.html', 
    extra_context=None):
    """Displays the changes between two revisions.
    
    """

    if extra_context is None:
        extra_context = {}

    # be group aware
    #group = getattr(request, "group", None)
    #if group:
    #    bridge = request.bridge
    #    group_base = bridge.group_base_template()
    #else:
    #    bridge = None
    #    group_base = None

    rev_a_id = request.GET.get('a', None)
    rev_b_id = request.GET.get('b', None)

    # Some stinky fingers manipulated the url
    if not rev_a_id or not rev_b_id:
        return HttpResponseBadRequest(_(u'Bad Request'))

    try:
        #if group:
        #    revision_queryset = group.content_objects(Revision, join="page")
        #    wikipage_queryset = group.content_objects(WikiPage)
        #else:
        #    revision_queryset = Revision.objects.all()
        #    wikipage_queryset = WikiPage.objects.all()

        rev_a = Revision.objects.get(pk=rev_a_id)
        rev_b = Revision.objects.get(pk=rev_b_id)
        page = WikiPage.objects.get(slug=slug)
    except ObjectDoesNotExist:
        raise Http404

    diff=[]
    if rev_a.content != rev_b.content:
        d = difflib.HtmlDiff()
        htmldiff = d.make_table(
            #rev_b.content.splitlines(),
            #rev_a.content.splitlines(),
            rev_b.content.splitlines(),
            rev_a.content.splitlines(),
            #'Original',
            #'Current',
            #lineterm='',
            #context=True,
        )
        #print htmldiff
        #diff.extend(["--- %s.%s" % (model.__name__, field),
        #             "+++ %s.%s" % (model.__name__, field)])
        difftext = '\n'.join(htmldiff)
        #print difftext

        #for line in d:
        #    print line
        #    diff.append(line)
        #diff = '\n'.join(diff)
    else:
        difftext = _(u'No changes were made between this two files.')

    template_context = {
        'page': page,
        'diff': htmldiff,
        'rev_a': rev_a,
        'rev_b': rev_b,
        #'group': group,
        #'group_base': group_base,
    }
    template_context.update(extra_context)
    return render_to_response(template_name, template_context,
        RequestContext(request))


# Some useful views
def revision_list(request, template_name='wiki/wiki_revision_list.html', 
    extra_context=None):
    """Displays a list of all recent revisions.
    
    """
    
    if extra_context is None:
        extra_context = {}

    # be group aware
    #group = getattr(request, "group", None)
    #if group:
    #    bridge = request.bridge
    #    group_base = bridge.group_base_template()
    #else:
    #    bridge = None
    #    group_base = None

    #if group:
    #    revision_list = group.content_objects(Revision, join="page")
    #else:
    #    revision_list = Revision.objects.all()

    revision_list = Revision.objects.all()
    template_context = {
        'revision_list': revision_list,
        #'group': group,
        #'group_base': group_base,
    }
    template_context.update(extra_context)
    return render_to_response(template_name, template_context,
        RequestContext(request))


def page_list(request, template_name='wiki/wiki_page_list.html',
    extra_context=None):
    """Displays all Pages
    
    Show the page list.
    """
    
    if extra_context is None:
        extra_context = {}

    # be group aware
    #group = getattr(request, "group", None)
    #if group:
    #    bridge = request.bridge
    #    group_base = bridge.group_base_template()
    #else:
    #    bridge = None
    #    group_base = None

    #if group:
    #    page_list = group.content_objects(WikiPage)
    #else:
    #    page_list = WikiPage.objects.all()
    
    page_list = WikiPage.objects.order_by('slug')

    template_context = {
        'page_list': page_list,
        'index_slug': DEFAULT_INDEX,
        #'group': group,
        #'group_base': group_base,
    }
    template_context.update(extra_context)
    return render_to_response(template_name, template_context, 
        RequestContext(request))
