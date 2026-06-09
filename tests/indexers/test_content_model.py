from pathlib import Path
from unittest.mock import MagicMock

import httpretty
import pytest
from plastron.client import Endpoint
from plastron.models import ContentModeledResource
from plastron.models.authorities import Subject, UMD_ARCHIVAL_COLLECTIONS
from plastron.models.page import File, Page
from plastron.models.umd import Item, AdminSet
from plastron.namespaces import umdtype, rdf, xsd, dcterms, owl
from plastron.rdfmapping.descriptors import DataProperty
from plastron.rdfmapping.properties import RDFDataProperty, RDFObjectProperty
from plastron.rdfmapping.resources import RDFResource
from plastron.repo import Repository, RepositoryResource
from plastron.validation.vocabularies import VocabularyTerm
from rdflib import URIRef, Literal

from solrizer.indexers import IndexerError, IndexerContext
from solrizer.indexers.content_model import (
    get_model_fields,
    get_data_fields,
    shorten_uri,
    get_object_fields,
    language_suffix,
    content_model_fields,
    get_display_values,
)


@pytest.mark.parametrize(
    ('uri', 'expected_value'),
    [
        (None, None),
        ('http://purl.org/dc/terms/title', 'dcterms:title'),
        ('http://example.com/foobar', 'http://example.com/foobar'),
    ],
)
def test_shorten_uri(uri, expected_value):
    assert shorten_uri(uri) == expected_value


@pytest.mark.parametrize(
    ('language', 'expected_value'),
    [
        (None, ''),
        ('en', '_en'),
        ('en-US', '_en_us'),
        ('ja-Latn', '_ja_latn'),
        ('jpn-LATN', '_ja_latn'),
        ('ger', '_de'),
    ],
)
def test_language_suffix(language, expected_value):
    assert language_suffix(language) == expected_value


def test_invalid_language_suffix():
    with pytest.raises(IndexerError):
        language_suffix('invalid::tag')


@pytest.mark.parametrize(
    ('attr_name', 'datatype', 'repeatable', 'values', 'expected_fields'),
    [
        ('title', None, False, ['Foobar'], {'title__txt': 'Foobar', 'title__display': ['Foobar']}),
        ('date', None, False, ['2024-08'], {'date__edtf': '2024-08'}),
        ('identifier', None, False, ['foobar'], {'identifier__id': 'foobar'}),
        ('handle', umdtype.handle, False, ['hdl:1903.1/123'], {'handle__id': 'hdl:1903.1/123'}),
        ('accession_number', umdtype.accessionNumber, False, ['123'], {'accession_number__id': '123'}),
        ('size', xsd.int, False, ['59'], {'size__int': 59}),
        ('size', xsd.integer, False, ['59'], {'size__int': 59}),
        ('size', xsd.long, False, ['59'], {'size__int': 59}),
        (
            'timestamp',
            xsd.dateTime,
            False,
            ['2024-08-16T14:54:18.240+00:00'],
            {
                'timestamp__time': '2024-08-16T14:54:18.240000Z',
            },
        ),
        (
            'value',
            None,
            False,
            [Literal('dog'), Literal('dog', lang='en'), Literal('der Hund', lang='de')],
            {
                'value__txt': 'dog',
                'value__txt_en': 'dog',
                'value__txt_de': 'der Hund',
                'value__display': ['dog', '[@en]dog', '[@de]der Hund'],
            },
        ),
        ('value', None, True, ['a', 'b', 'c'], {'value__txts': ['a', 'b', 'c'], 'value__display': ['a', 'b', 'c']}),
        (
            'value',
            None,
            True,
            [Literal('dog'), Literal('dog', lang='en'), Literal('der Hund', lang='de')],
            {
                'value__txts': ['dog'],
                'value__txts_en': ['dog'],
                'value__txts_de': ['der Hund'],
                'value__display': ['dog', '[@en]dog', '[@de]der Hund'],
            },
        ),
    ],
)
def test_get_data_properties(attr_name, datatype, repeatable, values, expected_fields):
    # repo = Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo')))
    resource = RDFResource(uri='http://example.com/fcrepo/foo')
    prop = RDFDataProperty(
        resource=resource,
        attr_name=attr_name,
        predicate=rdf.value,
        repeatable=repeatable,
        datatype=datatype,
    )
    prop.update(Literal(v, datatype=datatype) for v in values)
    fields = get_data_fields(prop)
    for k, v in fields.items():
        if isinstance(v, list):
            # multivalued fields are not guaranteed to come out of the RDF in the
            # same order they went in, so we just want to compare the values as sets
            # instead of lists
            assert set(v) == set(expected_fields[k])
        else:
            assert v == expected_fields[k]


def test_object_property_simple_no_curie():
    resource = RDFResource(uri='http://example.com/fcrepo/foo')
    prop = RDFObjectProperty(
        resource=resource,
        attr_name='same_as',
        predicate=owl.sameAs,
    )
    prop.add(URIRef('http://example.net/thing'))
    repo = MagicMock(spec=Repository)
    fields = get_object_fields(prop, repo)
    assert fields['same_as__uri'] == 'http://example.net/thing'
    assert fields['same_as__curie'] == 'http://example.net/thing'


def test_object_property_simple_with_curie():
    resource = RDFResource(uri='http://example.com/fcrepo/foo')
    prop = RDFObjectProperty(
        resource=resource,
        attr_name='same_as',
        predicate=owl.sameAs,
    )
    prop.add(URIRef('http://purl.org/dc/terms/Image'))
    repo = MagicMock(spec=Repository)
    fields = get_object_fields(prop, repo)
    assert fields['same_as__uri'] == 'http://purl.org/dc/terms/Image'
    assert fields['same_as__curie'] == 'dcterms:Image'


@httpretty.activate
def test_object_property_from_vocabulary(datadir: Path):
    httpretty.register_uri(
        method=httpretty.GET,
        uri=UMD_ARCHIVAL_COLLECTIONS.uri,
        body=(datadir / 'collection.json').read_text(),
        adding_headers={'Content-Type': 'application/ld+json'},
    )
    resource = RDFResource(uri='http://example.com/fcrepo/foo')
    prop = RDFObjectProperty(
        resource=resource,
        attr_name='archival_collection',
        predicate=dcterms.isPartOf,
        object_class=VocabularyTerm.from_vocab(UMD_ARCHIVAL_COLLECTIONS),
        values_from=UMD_ARCHIVAL_COLLECTIONS,
    )
    prop.add(URIRef('http://vocab.lib.umd.edu/collection#0051-MDHC'))
    repo = MagicMock(spec=Repository, endpoint=Endpoint('http://example.com/fcrepo'))
    fields = get_object_fields(prop, repo)
    assert fields['archival_collection__uri'] == 'http://vocab.lib.umd.edu/collection#0051-MDHC'
    assert fields['archival_collection__curie'] == 'http://vocab.lib.umd.edu/collection#0051-MDHC'
    assert fields['archival_collection__label__txt'] == 'Maryland Conservation Council records'
    assert fields['archival_collection__same_as__uris'] == ['http://hdl.handle.net/1903.1/1720']


def test_object_property_embedded():
    repo_resource = MagicMock(
        spec=RepositoryResource,
        url='http://example.com/fcrepo/foo',
        description_url=None,
    )
    resource = RDFResource(uri='http://example.com/fcrepo/foo')
    prop = RDFObjectProperty(
        resource=resource,
        attr_name='subject',
        predicate=dcterms.subject,
        embedded=True,
        object_class=Subject,
    )
    prop.add(
        Subject(
            uri=URIRef('http://example.com/fcrepo/foo#subject'),
            label=Literal('Test'),
        )
    )
    repo = MagicMock(spec=Repository, endpoint=Endpoint('http://example.com/fcrepo'))
    repo.__getitem__.return_value = repo_resource
    repo_resource.read.return_value = repo_resource

    fields = get_object_fields(prop, repo)
    assert fields['subject'] == [{
        'id': 'http://example.com/fcrepo/foo#subject',
        'subject__label__txt': 'Test',
        'subject__label__display': ['Test'],
    }]


def test_object_property_linked():
    resource = RDFResource(uri='http://example.com/fcrepo/foo')
    prop = RDFObjectProperty(
        resource=resource,
        attr_name='subject',
        predicate=dcterms.subject,
        object_class=Subject,
    )
    prop.add(URIRef('http://example.com/fcrepo/foo/bar'))
    repo = MagicMock(spec=Repository)
    repo.endpoint = Endpoint(url='http://example.com/fcrepo')
    repo_resource = MagicMock(
        spec=RepositoryResource,
        url='http://example.com/fcrepo/foo/bar',
        description_url=None,
    )
    repo.__getitem__.return_value = repo_resource
    repo_resource.read.return_value = repo_resource
    repo_resource.describe.return_value = Subject(
        uri=URIRef('http://example.com/fcrepo/foo/bar'),
        label=Literal('Bar'),
    )
    fields = get_object_fields(prop, repo)
    assert fields['subject'] == [{
        'id': 'http://example.com/fcrepo/foo/bar',
        'described_by__uri': 'http://example.com/fcrepo/foo/bar',
        'subject__label__txt': 'Bar',
        'subject__label__display': ['Bar'],
    }]


@pytest.mark.parametrize(
    ('obj', 'prefix', 'expected_fields'),
    [
        (
            Item(
                uri='http://example.com/fcrepo/rest/item',
                title=Literal('Test Object'),
                handle=Literal('hdl:1903.1/123', datatype=umdtype.handle),
                accession_number=Literal('123', datatype=umdtype.accessionNumber),
                date=Literal('2024-08'),
                identifier=Literal('tst-123'),
                archival_collection=URIRef('http://vocab.lib.umd.edu/collection#0051-MDHC'),
                created_by=Literal('plastron'),
                last_modified_by=Literal('archelon'),
            ),
            'object__',
            {
                'content_model_name__str': 'Item',
                'described_by__uri': 'http://example.com/fcrepo/rest/item',
                'object__rdf_type__uris': ['http://vocab.lib.umd.edu/model#Item', 'http://pcdm.org/models#Object'],
                'object__rdf_type__curies': ['umd:Item', 'pcdm:Object'],
                'object__title__txt': 'Test Object',
                'object__title__display': ['Test Object'],
                'object__accession_number__id': '123',
                'object__date__edtf': '2024-08',
                'object__handle__id': 'hdl:1903.1/123',
                'object__identifier__ids': ['tst-123'],
                'object__archival_collection__uri': 'http://vocab.lib.umd.edu/collection#0051-MDHC',
                'object__archival_collection__curie': 'http://vocab.lib.umd.edu/collection#0051-MDHC',
                'object__archival_collection__label__txt': 'Maryland Conservation Council records',
                'object__archival_collection__label__display': ['Maryland Conservation Council records'],
                'object__archival_collection__same_as__uris': ['http://hdl.handle.net/1903.1/1720'],
                'object__archival_collection__same_as__curies': ['http://hdl.handle.net/1903.1/1720'],
                'object__created_by__str': 'plastron',
                'object__last_modified_by__str': 'archelon',
            },
        ),
        (
            File(
                uri='http://example.com/fcrepo/rest/file',
                filename=Literal('0001.tif'),
                mime_type=Literal('image/tiff'),
            ),
            'file__',
            {
                'content_model_name__str': 'File',
                'described_by__uri': 'http://example.com/fcrepo/rest/file/fcr:metadata',
                'file__rdf_type__uris': ['http://pcdm.org/models#File'],
                'file__rdf_type__curies': ['pcdm:File'],
                'file__filename__str': '0001.tif',
                'file__mime_type__str': 'image/tiff',
            },
        ),
    ],
)
@httpretty.activate()
def test_get_model_fields(obj, prefix, expected_fields, datadir, register_uri_for_reading):
    register_uri_for_reading(
        uri='http://vocab.lib.umd.edu/collection#',
        content_type='application/ld+json',
        body=(datadir / 'collection.json').read_text(),
    )
    repo_resource = MagicMock(
        spec=RepositoryResource,
        url=obj.uri,
        description_url=f'{obj.uri}/fcr:metadata' if isinstance(obj, File) else None,
    )
    repo = MagicMock(spec=Repository, endpoint=Endpoint('http://example.com/fcrepo'))
    repo.__getitem__.return_value = repo_resource
    repo_resource.read.return_value = repo_resource
    fields = get_model_fields(obj, repo, prefix=prefix)
    for k, v in fields.items():
        if isinstance(v, list):
            assert set(v) == set(expected_fields[k])
        else:
            assert v == expected_fields[k]


class BasicResource(ContentModeledResource):
    model_name = 'TestingResource'


@pytest.mark.parametrize(
    ('url', 'description_url', 'expected_value'),
    [
        (
            'http://example.com/fcrepo/rest/123',
            'http://example.com/fcrepo/rest/123/fcr:metadata',
            'http://example.com/fcrepo/rest/123/fcr:metadata',
        ),
        # when the `description_url` is None (i.e., this is an RDF source),
        # should fall back to using the plain `url` for the `described_by__uri` field
        (
            'http://example.com/fcrepo/rest/123',
            None,
            'http://example.com/fcrepo/rest/123',
        ),
    ]
)
def test_described_by(url, description_url, expected_value):
    mock_resource = MagicMock(spec=RepositoryResource)
    mock_resource.url = url
    mock_resource.description_url = description_url
    repo = MagicMock(spec=Repository, endpoint=Endpoint('http://example.com/fcrepo'))
    repo.__getitem__.return_value = mock_resource
    mock_resource.read.return_value = mock_resource
    mock_resource.describe.return_value = BasicResource(uri='http://example.com/fcrepo')
    context = IndexerContext(
        repo=repo,
        resource=mock_resource,
        model_class=BasicResource,
        doc={'id': 'foo'},
        config={},
    )
    fields = content_model_fields(context)
    assert fields['described_by__uri'] == expected_value


@pytest.mark.parametrize(
    ('values', 'preferred_language', 'expected_value'),
    [
        ([Literal('b'), Literal('c'), Literal('a')], None, ['a', 'b', 'c']),
        # case insensitive for values
        ([Literal('B'), Literal('C'), Literal('a')], None, ['a', 'B', 'C']),
        # sort language tags first
        (
            [Literal('b', lang='de'), Literal('c'), Literal('a', lang='ja')],
            None,
            ['[@de]b', '[@ja]a', 'c'],
        ),
        # preferred language listed first
        (
            [Literal('b', lang='de'), Literal('c'), Literal('a', lang='ja')],
            'ja',
            ['[@ja]a', '[@de]b', 'c'],
        ),
        # language tags are normalized
        (
            [Literal('b', lang='en'), Literal('c', lang='EN'), Literal('a')],
            None,
            ['[@en]b', '[@en]c', 'a'],
        ),
        (
            [Literal('b', lang='de'), Literal('c'), Literal('a', lang='ja')],
            'JA',
            ['[@ja]a', '[@de]b', 'c'],
        ),
        (
            [Literal('b', lang='de'), Literal('c'), Literal('a', lang='ja')],
            'jpn',
            ['[@ja]a', '[@de]b', 'c'],
        ),
        (
            [Literal('b', lang='de'), Literal('c'), Literal('a', lang='af')],
            'ger',
            ['[@de]b', '[@af]a', 'c'],
        ),
    ]
)
def test_get_display_values(values, preferred_language, expected_value):
    assert get_display_values(values, preferred_language) == expected_value


class SimpleModel(ContentModeledResource):
    model_name = 'SimpleModel'

    title = DataProperty(dcterms.title)
    language = DataProperty(dcterms.language)


def test_get_model_fields_display_value_with_resource_language():
    mock_repo = MagicMock(spec=Repository, endpoint=Endpoint('http://example.com/fcrepo/rest'))
    # "@en" sorts first (ahead of "@de") since it is the language of the resource
    obj = SimpleModel(language=Literal('en'), title=[Literal('Hund', lang='de'), Literal('Dog', 'en')])
    fields = get_model_fields(obj, mock_repo)
    assert fields['title__display'] == ['[@en]Dog', '[@de]Hund']


def test_get_model_fields_display_value_without_resource_language():
    mock_repo = MagicMock(spec=Repository, endpoint=Endpoint('http://example.com/fcrepo/rest'))
    # "@de" sorts before "@en" since there is no resource language
    obj = SimpleModel(title=[Literal('Hund', lang='de'), Literal('Dog', 'en')])
    fields = get_model_fields(obj, mock_repo)
    assert fields['title__display'] == ['[@de]Hund', '[@en]Dog']


@pytest.mark.parametrize(
    ('obj', 'expected_field', 'expected_value'),
    [
        (Item(title=Literal('bar')), 'object__title__txt', 'bar'),
        (Page(title=Literal('foo')), 'page__title__txt', 'foo'),
        (File(filename=Literal('foo.txt')), 'file__filename__str', 'foo.txt'),
        (AdminSet(title=Literal('stuff')), 'adminset__title__txt', 'stuff'),
    ]
)
def test_content_model_fields(get_mock_context, obj, expected_field, expected_value):
    doc = content_model_fields(get_mock_context(obj))
    assert expected_field in doc
    assert doc[expected_field] == expected_value
