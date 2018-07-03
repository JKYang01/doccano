import json

from django_filters.rest_framework import DjangoFilterBackend
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from rest_framework import viewsets, filters, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser

from .models import Label, Document, Project
from .models import DocumentAnnotation
from .serializers import LabelSerializer, ProjectSerializer, DocumentSerializer, AnnotationSerializer


class IndexView(TemplateView):
    template_name = 'index.html'


class InboxView(LoginRequiredMixin, TemplateView):
    template_name = 'annotation.html'


class ProjectsView(LoginRequiredMixin, ListView):
    model = Project
    paginate_by = 100
    template_name = 'projects.html'


class ProjectAdminView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'project_admin.html'


class RawDataAPI(View):

    def post(self, request, *args, **kwargs):
        """Upload data."""
        f = request.FILES['file']
        content = ''.join(chunk.decode('utf-8') for chunk in f.chunks())
        for line in content.split('\n'):
            j = json.loads(line)
            Document(text=j['text']).save()

        return JsonResponse({'status': 'ok'})


class DataDownloadAPI(View):

    def get(self, request, *args, **kwargs):
        annotated_docs = [a.as_dict() for a in Annotation.objects.filter(manual=True)]
        json_str = json.dumps(annotated_docs)
        response = HttpResponse(json_str, content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename=annotation_data.json'

        return response


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer

    @action(methods=['get'], detail=True)
    def progress(self, request, pk=None):
        project = self.get_object()
        docs = project.documents.all()
        remaining = docs.filter(labels__isnull=True).count()
        return Response({'total': docs.count(), 'remaining': remaining})


class ProjectLabelsAPI(generics.ListCreateAPIView):
    queryset = Label.objects.all()
    serializer_class = LabelSerializer
    pagination_class = None

    def get_queryset(self):
        project_id = self.kwargs['project_id']
        queryset = self.queryset.filter(project=project_id)

        return queryset

    def perform_create(self, serializer):
        project_id = self.kwargs['project_id']
        project = get_object_or_404(Project, pk=project_id)
        serializer.save(project=project)


class ProjectLabelAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = Label.objects.all()
    serializer_class = LabelSerializer

    def get_queryset(self):
        project_id = self.kwargs['project_id']
        queryset = self.queryset.filter(project=project_id)

        return queryset

    def get_object(self):
        label_id = self.kwargs['label_id']
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, pk=label_id)
        self.check_object_permissions(self.request, obj)

        return obj


class ProjectDocsAPI(generics.ListCreateAPIView):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('text', )

    def get_queryset(self):
        project_id = self.kwargs['project_id']
        queryset = self.queryset.filter(project=project_id)

        return queryset


class AnnotationsAPI(generics.ListCreateAPIView):
    queryset = DocumentAnnotation.objects.all()
    serializer_class = AnnotationSerializer
    pagination_class = None

    def get_queryset(self):
        doc_id = self.kwargs['doc_id']
        queryset = self.queryset.filter(data=doc_id)
        return queryset

    def post(self, request, *args, **kwargs):
        doc_id = self.kwargs['doc_id']
        label_id = request.data['label_id']
        doc = Document.objects.get(id=doc_id)
        label = Label.objects.get(id=label_id)
        annotation = DocumentAnnotation(data=doc, label=label, manual=True)
        annotation.save()
        serializer = self.serializer_class(annotation)

        return Response(serializer.data)


class AnnotationAPI(generics.RetrieveUpdateDestroyAPIView):
    queryset = DocumentAnnotation.objects.all()
    serializer_class = AnnotationSerializer

    def get_queryset(self):
        doc_id = self.kwargs['doc_id']
        queryset = self.queryset.filter(data=doc_id)

        return queryset

    def get_object(self):
        annotation_id = self.kwargs['annotation_id']
        queryset = self.filter_queryset(self.get_queryset())
        obj = get_object_or_404(queryset, pk=annotation_id)
        self.check_object_permissions(self.request, obj)

        return obj
