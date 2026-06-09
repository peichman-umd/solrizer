from collections.abc import Mapping
from unittest.mock import MagicMock
from uuid import uuid4

import plastron.models.authorities
import plastron.validation.vocabularies
import pytest
from httpretty import httpretty
from plastron.client import Endpoint, Client
from plastron.models import ContentModeledResource
from plastron.repo import RepositoryResource, Repository
from plastron.repo.aggregation import ProxiedResourceIterator
from plastron.repo.pcdm import PCDMObjectResource
from rdflib import Graph, URIRef

from solrizer.indexers import SolrFields, IndexerContext
from solrizer.web import create_app


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('SOLRIZER_FCREPO_ENDPOINT', 'http://localhost:8080/fcrepo/rest')
    monkeypatch.setenv('SOLRIZER_FCREPO_JWT_TOKEN', '')
    monkeypatch.setenv('SOLRIZER_FCREPO_JWT_SECRET', str(uuid4()))
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def proxies() -> SolrFields:
    return {
        'proxy__proxy_for__uri': 'url1',
        'proxy__next': [{
            'proxy__proxy_for__uri': 'url2',
            'proxy__next': [{
                'proxy__proxy_for__uri': 'url3',
            }]
        }]
    }


@pytest.fixture
def create_mock_repo():
    def _create_mock_repo(
        paths: Mapping[str, ContentModeledResource | tuple[ContentModeledResource, type[RepositoryResource]]] = None,
        repo_url: str = 'http://example.com/fcrepo',
    ) -> Repository:
        uri_mapping = {}

        def _lookup_path(key):
            if isinstance(key, slice):
                return str(key.start).replace(repo_url, '')
            else:
                return str(key).replace(repo_url, '')

        def _get_resource(key):
            return uri_mapping[URIRef(repo_url + _lookup_path(key))]

        mock_repo = MagicMock(spec=Repository)
        mock_repo.__getitem__.side_effect = _get_resource
        mock_repo.get_resource.side_effect = _get_resource
        mock_repo.endpoint = Endpoint(repo_url)
        for path, obj_def in (paths or {}).items():
            if isinstance(obj_def, tuple):
                obj = obj_def[0]
                cls = obj_def[1]
            else:
                obj = obj_def
                cls = PCDMObjectResource
            resource = MagicMock(spec=cls)
            resource.repo = mock_repo
            resource.convert_to.return_value = resource
            resource.read.return_value = resource
            resource.describe.return_value = obj
            resource.path = path
            resource._graph = obj.graph
            resource.get_sequence.return_value = ProxiedResourceIterator(resource)
            uri_mapping[URIRef(repo_url + path)] = resource

        return mock_repo
    return _create_mock_repo


@pytest.fixture
def mock_vocabularies(monkeypatch, shared_datadir):
    def _get_vocabulary_graph(uri: str):
        basename = uri.split('#', 1)[0].rsplit('/', 1)[-1]
        graph = Graph()
        with (shared_datadir / f'{basename}.json').open() as fh:
            graph.parse(file=fh)
        return graph

    monkeypatch.setattr(plastron.validation.vocabularies, 'get_vocabulary_graph', _get_vocabulary_graph)

    return _get_vocabulary_graph


@pytest.fixture
def get_mock_resource():
    def _mock_resource(path, obj, resource_class=RepositoryResource):
        mock_resource = MagicMock(spec=resource_class, path=path)
        mock_resource.read.return_value = mock_resource
        mock_resource.convert_to.return_value = mock_resource
        mock_resource.describe.return_value = obj
        return mock_resource
    return _mock_resource


@pytest.fixture
def get_mock_context(get_mock_resource):
    def _mock_context(obj, resource=None, repo=None):
        if resource is None:
            resource = get_mock_resource('/foo', obj)
        if repo is None:
            repo = Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo')))
        return IndexerContext(
            repo=repo,
            resource=resource,
            model_class=obj.__class__,
            doc={},
            config={},
        )
    return _mock_context


@pytest.fixture
def register_uri_for_reading():
    def _register_uri_for_reading(uri: str, content_type: str, body: str):
        httpretty.register_uri(
            method=httpretty.HEAD,
            uri=uri,
            adding_headers={'Content-Type': content_type},
        )
        httpretty.register_uri(
            method=httpretty.GET,
            uri=uri,
            body=body,
            adding_headers={'Content-Type': content_type},
        )
    return _register_uri_for_reading


@pytest.fixture
def context_with_date():
    def _context(edtf_value):
        return IndexerContext(
            repo=MagicMock(spec=Repository),
            resource=MagicMock(spec=RepositoryResource),
            model_class=ContentModeledResource,
            doc={
                'date__edtf': edtf_value,
            },
            config={},
        )

    return _context
