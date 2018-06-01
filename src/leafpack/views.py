# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import re
from dataloaderinterface.models import SiteRegistration
from django.views.generic.edit import UpdateView, CreateView, DeleteView, FormView, BaseDetailView
from django.views.generic.detail import DetailView
from django.shortcuts import reverse, redirect
from django.http import HttpResponse
from django.core.management import call_command
from django.core.exceptions import ObjectDoesNotExist

from .models import LeafPack, Macroinvertebrate, LeafPackType
from .forms import LeafPackForm, LeafPackBugForm, LeafPackBugFormFactory, LeafPackBug
from dataloaderinterface.views import LoginRequiredMixin

from csv_writer import LeafPackCSVWriter


class LeafPackViewMixin(object):

    def __init__(self, **kwargs):
        self.request = None
        self.kwargs = kwargs

        if kwargs and len(kwargs):
            for key, value in kwargs:
                setattr(self, key, value)

    def forms_valid(self, forms):
        is_valid = True
        for form in forms:
            if not form.is_valid():
                is_valid = False
        return is_valid

    def get_bug_count_forms(self, leafpack=None):
        re_bug_name = re.compile(r'^(?P<bug_name>.*)-bug_count')
        form_data = list()
        for key, value in self.request.POST.iteritems():
            if 'bug_count' in key:
                form_data.append((re_bug_name.findall(key)[0], value))

        bug_forms = list()
        for data in form_data:
            bug = Macroinvertebrate.objects.get(scientific_name=data[0])
            count = data[1]

            form = LeafPackBugForm(data={'bug_count'.format(bug.scientific_name): count})
            if leafpack is not None:
                form.instance = LeafPackBug.objects.get(leaf_pack=leafpack, bug=bug)
            else:
                form.instance.bug = bug

            bug_forms.append(form)

        return bug_forms

    def get_leafpack_types_other(self):
        lp_types = self.request.POST.get('types', None)

        if lp_types is None:
            return []


class LeafPackUpdateCreateMixin(LeafPackViewMixin):

    def get_object(self):
        return LeafPack.objects.get(id=self.kwargs['pk'])

    def add_types_other(self):
        """
        Creates new LeafPackTypes from self.request.POST['types_other'] (i.e., custom leaf pack types entered by user)
        :return: None
        """

        leafpack_types_other = self.request.POST.get('types_other', '')
        for other_type in leafpack_types_other.split(','):
            try:
                _ = LeafPackType.objects.get(name=other_type.strip())
            except ObjectDoesNotExist:
                LeafPackType.objects.create(name=other_type.strip(), created_by=self.request.user)


class LeafPackDetailView(DetailView):
    """
    Detail View
    """
    template_name = 'leafpack/leafpack_detail.html'
    slug_field = 'sampling_feature_code'
    model = LeafPack

    def get_object(self, queryset=None):
        return LeafPack.objects.get(id=self.kwargs['pk'])

    def get_taxon(self):
        lptaxons = []
        leafpack = self.get_object()

        # order taxon by pollution_tolerance, then by sort_priority in descending order
        taxon = Macroinvertebrate.objects.filter(family_of=None)\
            .order_by('pollution_tolerance')\
            .order_by('-sort_priority')

        # get subcategories of taxon
        for parent in taxon:
            try:
                parent_taxon = LeafPackBug.objects.get(leaf_pack=leafpack, bug=parent)
            except ObjectDoesNotExist:
                continue

            child_taxons = []
            for child in parent.families.all().order_by('common_name'):

                try:
                    lpg = LeafPackBug.objects.get(leaf_pack=leafpack, bug=child)
                except ObjectDoesNotExist:
                    """
                    ObjectDoesNotExist is raised when a taxon is added to the database after a leafpack experiment
                    was created. In such cases, a new LeafPackBug object needs to be created that links 'leafpack' 
                    and the new taxon.
                    """
                    lpg = LeafPackBug.objects.create(leaf_pack=leafpack, bug=child, bug_count=0)

                child_taxons.append(lpg)

            lptaxons.append((parent_taxon, child_taxons))

        return lptaxons

    def get_context_data(self, **kwargs):
        context = super(LeafPackDetailView, self).get_context_data(**kwargs)
        context['leafpack'] = self.get_object()
        context['leafpack_bugs'] = self.get_taxon()
        context['sampling_feature_code'] = self.get_object().site_registration.sampling_feature_code

        return context

    def get(self, request, *args, **kwargs):
        # call_command('update_taxon')
        return super(LeafPackDetailView, self).get(request, *args, **kwargs)


class LeafPackCreateView(LeafPackUpdateCreateMixin, CreateView):
    """
    Create View
    """
    form_class = LeafPackForm
    template_name = 'leafpack/leafpack_registration.html'
    slug_field = 'sampling_feature_code'
    object = None

    def form_invalid(self, leafpack_form, taxon_forms):
        context = self.get_context_data(form=leafpack_form, taxon_forms=taxon_forms)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):

        # if 'leafpack_form' is in kwargs, that means self.form_invalid was most likely called due to a failed POST request
        if 'form' in kwargs:
            self.object = kwargs['form'].instance

        context = super(LeafPackCreateView, self).get_context_data(**kwargs)

        context['sampling_feature_code'] = self.kwargs[self.slug_field]

        if self.object is None:
            site_registration = SiteRegistration.objects.get(sampling_feature_code=self.kwargs[self.slug_field])
            context['form'] = LeafPackForm(initial={'site_registration': site_registration})

        if 'taxon_forms' in kwargs:
            context['taxon_forms'] = LeafPackBugFormFactory.formset_factory(taxon_forms=kwargs.pop('taxon_forms'))
        else:
            context['taxon_forms'] = LeafPackBugFormFactory.formset_factory()

        return context

    def post(self, request, *args, **kwargs):

        self.add_types_other()

        leafpack_form = self.get_form()
        bug_forms = self.get_bug_count_forms()

        if self.forms_valid([leafpack_form] + bug_forms):
            leafpack_form.save()

            for bug_form in bug_forms:
                LeafPackBug.objects.create(bug=bug_form.instance.bug, leaf_pack=leafpack_form.instance,
                                           bug_count=bug_form.cleaned_data['bug_count'])

            return redirect(reverse('site_detail', kwargs={'sampling_feature_code':
                                                           self.kwargs['sampling_feature_code']}))

        return self.form_invalid(leafpack_form, bug_forms)


class LeafPackUpdateView(LoginRequiredMixin, LeafPackUpdateCreateMixin, UpdateView):
    """
    Update view
    """
    form_class = LeafPackForm
    template_name = 'leafpack/leafpack_registration.html'
    slug_field = 'sampling_feature_code'
    object = None

    def form_invalid(self, form):
        response = super(LeafPackUpdateView, self).form_invalid(form)
        return response

    def get_context_data(self, **kwargs):
        context = super(LeafPackUpdateView, self).get_context_data(**kwargs)

        context['sampling_feature_code'] = self.kwargs[self.slug_field]
        context['taxon_forms'] = LeafPackBugFormFactory.formset_factory(self.get_object())

        if 'leafpack' not in context:
            context['leafpack'] = self.get_object()

        return context

    def post(self, request, *args, **kwargs):

        self.add_types_other()

        leafpack_form = LeafPackForm(request.POST, instance=self.get_object())
        bug_forms = self.get_bug_count_forms()

        if self.forms_valid([leafpack_form] + bug_forms):
            leafpack_form.save()

            for bug_form in bug_forms:
                bug = LeafPackBug.objects.get(bug=bug_form.instance.bug, leaf_pack=leafpack_form.instance)
                bug.bug_count = bug_form.cleaned_data['bug_count']
                bug.save()

            return redirect(reverse('leafpack:view', kwargs={self.slug_field: self.kwargs[self.slug_field],
                                                             'pk': self.get_object().id}))

        return self.form_invalid(leafpack_form)


class LeafPackDeleteView(LoginRequiredMixin, DeleteView):
    """
    Delete view
    """
    slug_field = 'sampling_feature_code'

    def get_object(self, queryset=None):
        return LeafPack.objects.get(id=self.kwargs['pk'])

    def post(self, request, *args, **kwargs):
        leafpack = self.get_object()
        leafpack.delete()
        return redirect(reverse('site_detail', kwargs={self.slug_field: self.kwargs[self.slug_field]}))


def download_leafpack_csv(request, sampling_feature_code, pk):
    """
    Download handler that uses csv_writer.py to parse out a leaf pack expirement into a csv file.

    :param request: the request object
    :param sampling_feature_code: the first URL parameter
    :param pk: the second URL parameter and id of the leafpack experiement to download 
    """
    leafpack = LeafPack.objects.get(id=pk)
    site = SiteRegistration.objects.get(sampling_feature_code=sampling_feature_code)

    writer = LeafPackCSVWriter(leafpack, site)
    writer.write()

    # filename format: {Sampling Feature Code}_{Placement date}_{leafpack ID padded with zeros}.csv
    filename = '{}_{}_{:03d}.csv'.format(sampling_feature_code, leafpack.placement_date, int(pk))

    response = HttpResponse(writer.read(), content_type='application/csv')
    response['Content-Disposition'] = 'inline; filename={0}'.format(filename)

    return response
