from unittest.mock import MagicMock

import pytest
from plastron.client import Client, Endpoint
from plastron.models.ldp import LDPContainer
from plastron.models.ore import Proxy
from plastron.models.umd import Item
from plastron.repo import Repository
from rdflib import URIRef

from solrizer.indexers import IndexerContext
from solrizer.indexers.iiif_links import iiif_identifier, iiif_links_fields, get_first_file_identifier


@pytest.mark.parametrize(
    ('path', 'prefix', 'expected_identifier'),
    [
        ('/foo/bar', 'fcrepo:', 'fcrepo:foo:bar'),
        ('/foo', 'fcrepo:', 'fcrepo:foo'),
        ('/foo', '', 'foo'),
    ]
)
def test_iiif_identifier(path, prefix, expected_identifier):
    assert iiif_identifier(path, prefix) == expected_identifier


@pytest.mark.parametrize(
    ('files', 'expected_id'),
    [
        # preservation master first
        (
            [
                ('/master', ['pcdm:File', 'pcdmuse:PreservationMasterFile'], 'image/tiff'),
                ('/pdf', ['pcdm:File'], 'application/pdf'),
            ],
            'fcrepo:master',
        ),
        # preservation master second
        (
            [
                ('/pdf', ['pcdm:File'], 'application/pdf'),
                ('/master', ['pcdm:File', 'pcdmuse:PreservationMasterFile'], 'image/tiff'),
            ],
            'fcrepo:master',
        ),
        # preservation master after TIFF
        (
            [
                ('/tiff', ['pcdm:File'], 'image/tiff'),
                ('/master', ['pcdm:File', 'pcdmuse:PreservationMasterFile'], 'image/tiff'),
            ],
            'fcrepo:master',
        ),
        # TIFF before JPEG, no preservation master
        (
            [
                ('/tiff', ['pcdm:File'], 'image/tiff'),
                ('/jpeg', ['pcdm:File'], 'image/jpeg'),
            ],
            'fcrepo:tiff',
        ),
        # TIFF after JPEG, no preservation master
        (
            [
                ('/jpeg', ['pcdm:File'], 'image/jpeg'),
                ('/tiff', ['pcdm:File'], 'image/tiff'),
            ],
            'fcrepo:tiff',
        ),
        # only TIFF, no preservation master
        (
            [
                ('/tiff', ['pcdm:File'], 'image/tiff'),
            ],
            'fcrepo:tiff',
        ),
        # only JPEG, no preservation master
        (
            [
                ('/jpeg', ['pcdm:File'], 'image/jpeg'),
            ],
            'fcrepo:jpeg',
        ),
        # other image only
        (
            [
                ('/png', ['pcdm:File'], 'image/png'),
            ],
            'fcrepo:png',
        ),
        # preservation master not a TIFF file
        (
            [
                ('/pdf', ['pcdm:File', 'pcdmuse:PreservationMasterFile'], 'application/pdf'),
            ],
            'static:unavailable',
        ),
        # no suitable image file
        (
            [
                ('/pdf', ['pcdm:File'], 'application/pdf'),
                ('/xml', ['pcdm:File', 'pcdmuse:ExtractedText'], 'application/xml'),
            ],
            'static:unavailable',
        ),
        # no files
        (
            [],
            'static:unavailable',
        ),
    ]
)
def test_get_file_identifier(files, expected_id):
    page = {
        'page__has_file': [
            {
                'id': f'http://example.com/fcrepo/rest{repo_path}',
                'file__rdf_type__curies': rdf_types,
                'file__mime_type__str': mime_type,
            }
            for repo_path, rdf_types, mime_type in files
        ]
    }
    mock_context = MagicMock(
        spec=IndexerContext,
        config={'IIIF_IDENTIFIER_PREFIX': 'fcrepo:'},
        repo=Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo/rest'))),
    )
    iiif_id = get_first_file_identifier(mock_context, page)
    assert iiif_id == expected_id


@pytest.fixture
def mock_repo(create_mock_repo):
    return create_mock_repo({
        '/proxy1': Proxy(proxy_for=URIRef('/url1'), next=URIRef('/proxy2')),
        '/proxy2': Proxy(proxy_for=URIRef('/url2'), next=URIRef('/proxy3')),
        '/proxy3': Proxy(proxy_for=URIRef('/url3')),
        '/foo': Item(first=URIRef('/proxy1')),
        '/foo/f': LDPContainer(),
        '/foo/m': LDPContainer(),
    })


@pytest.fixture
def create_ctx(mock_repo):
    def _ctx(members):
        return IndexerContext(
            repo=mock_repo,
            resource=mock_repo['/foo'],
            model_class=Item,
            doc={
                'id': 'http://example.com/fcrepo/foo',
                'object__has_member': members,
            },
            config={
                'IIIF_IDENTIFIER_PREFIX': 'fcrepo:',
                'IIIF_THUMBNAIL_URL_PATTERN': 'http://iiif.example.com/thumbnail/{+id}',
                'IIIF_MANIFESTS_URL_PATTERN': 'http://iiif.example.com/manifest/{+id}',
            },
        )

    return _ctx


def test_iiif_links_fields(proxies, create_ctx):
    members = [
        {'id': '/url1', 'page__title__txt': 'Bar 1', 'page__has_file': [
            {
                'id': 'http://example.com/fcrepo/foo/obj1/fileX',
                'file__rdf_type__curies': ['pcdmuse:PreservationMasterFile'],
                'file__mime_type__str': 'image/tiff',
            },
        ]},
        {'id': '/url2', 'page__title__txt': 'Bar 2', 'page__has_file': [
            {
                'id': 'http://example.com/fcrepo/foo/obj2/fileX',
                'file__rdf_type__curies': ['pcdmuse:PreservationMasterFile'],
                'file__mime_type__str': 'image/tiff',
            },
        ]},
        {'id': '/url3', 'page__title__txt': 'Bar 3', 'page__has_file': [
            {
                'id': 'http://example.com/fcrepo/foo/obj3/fileX',
                'file__rdf_type__curies': ['pcdmuse:PreservationMasterFile'],
                'file__mime_type__str': 'image/tiff',
            },
        ]},
    ]
    fields = iiif_links_fields(create_ctx(members))
    assert fields == {
        'iiif_manifest__id': 'fcrepo:foo',
        'iiif_manifest__uri': 'http://iiif.example.com/manifest/fcrepo:foo',
        'iiif_thumbnail_sequence__ids': [
            'fcrepo:foo:obj1:fileX',
            'fcrepo:foo:obj2:fileX',
            'fcrepo:foo:obj3:fileX',
        ],
        'iiif_thumbnail_sequence__uris': [
            'http://iiif.example.com/thumbnail/fcrepo:foo:obj1:fileX',
            'http://iiif.example.com/thumbnail/fcrepo:foo:obj2:fileX',
            'http://iiif.example.com/thumbnail/fcrepo:foo:obj3:fileX',
        ]
    }


def test_iiif_links_no_file_on_page(proxies, create_ctx):
    members = [
        {'id': '/url1', 'page__title__txt': 'Bar 1'},
        {'id': '/url2', 'page__title__txt': 'Bar 2', 'page__has_file': [
            {
                'id': 'http://example.com/fcrepo/foo/obj2/fileX',
                'file__rdf_type__curies': ['pcdmuse:PreservationMasterFile'],
                'file__mime_type__str': 'image/tiff',
            },
        ]},
        {'id': '/url3', 'page__title__txt': 'Bar 3', 'page__has_file': [
            {
                'id': 'http://example.com/fcrepo/foo/obj3/fileX',
                'file__rdf_type__curies': ['pcdmuse:PreservationMasterFile'],
                'file__mime_type__str': 'image/tiff',
            },
        ]},
    ]
    fields = iiif_links_fields(create_ctx(members))
    assert fields == {
        'iiif_manifest__id': 'fcrepo:foo',
        'iiif_manifest__uri': 'http://iiif.example.com/manifest/fcrepo:foo',
        'iiif_thumbnail_sequence__ids': [
            'static:unavailable',
            'fcrepo:foo:obj2:fileX',
            'fcrepo:foo:obj3:fileX',
        ],
        'iiif_thumbnail_sequence__uris': [
            'http://iiif.example.com/thumbnail/static:unavailable',
            'http://iiif.example.com/thumbnail/fcrepo:foo:obj2:fileX',
            'http://iiif.example.com/thumbnail/fcrepo:foo:obj3:fileX',
        ]
    }
