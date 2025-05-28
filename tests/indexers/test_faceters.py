from unittest.mock import MagicMock

import pytest
from plastron.client import Client, Endpoint
from plastron.models.pcdm import PCDMObject
from plastron.models import ContentModeledResource
from plastron.models.umd import AdminSet, Item
from plastron.namespaces import rdf, dcterms, rdf, umdaccess
from plastron.rdfmapping.properties import RDFDataProperty, RDFObjectProperty
from plastron.rdfmapping.resources import RDFResource
from plastron.repo import Repository, RepositoryResource
from plastron.repo.pcdm import PCDMObjectResource
from rdflib import Literal, URIRef

from solrizer.faceters import (
    AdminSetFacet,
    CensorshipFacet,
    FacetBase,
    OCRFacet,
    PresentationSetFacet,
    PublicationStatusFacet,
    VisibilityFacet,
    concat_values,
    get_labels,
    language_name,
    rights_statement_label,
)
from solrizer.indexers import IndexerContext


@pytest.fixture
def data_prop():
    return RDFDataProperty(
        resource=RDFResource(),
        attr_name='foo',
        predicate=rdf.value,
        repeatable=True,
    )


def test_cant_instantiate_facet_base():
    f = FacetBase(MagicMock(spec=IndexerContext))
    with pytest.raises(NotImplementedError):
        f.get_values()


@pytest.mark.parametrize(
    ('code', 'expected_value'),
    [
        ('en', 'English'),
        ('eng', 'English'),
        # only handles the language portion
        # anything with a script is returned as-is
        ('ja-Latn', 'ja-Latn'),
    ]
)
def test_language_name(code, expected_value):
    assert language_name(code) == expected_value


def test_rights_statement_label_unknown_uri(mock_vocabularies):
    assert rights_statement_label('http://example.com/rights/foobar') == 'http://example.com/rights/foobar'


@pytest.mark.parametrize(
    ('values', 'expected_string'),
    [
        ([Literal('foo'), Literal('bar'), Literal('abc')], 'abc / bar / foo'),
        (
            [Literal('foo1', lang='ja-Latn'), Literal('foo2', lang='ja'), Literal('foo3', lang='en')],
            'foo3 / foo2 / foo1',
        ),
    ]
)
def test_concat_values(data_prop, values, expected_string):
    data_prop.extend(values)
    assert concat_values(data_prop) == expected_string


def test_concat_values_with_separator(data_prop):
    data_prop.extend([Literal('A'), Literal('B')])
    assert concat_values(data_prop, '---') == 'A---B'


def test_get_labels():
    obj_prop = RDFObjectProperty(
        resource=RDFResource(),
        attr_name='creator',
        predicate=dcterms.creator,
        repeatable=True,
        object_class=RDFResource,
    )
    obj_prop.add(RDFResource(label=Literal('Riley')))
    obj_prop.add(RDFResource(label=Literal('Erin')))
    obj_prop.add(RDFResource(label=[Literal('John'), Literal('Paul')]))

    assert get_labels(obj_prop) == ['Riley', 'Erin', 'John / Paul']


@pytest.mark.parametrize(
    ('obj', 'expected_values'),
    [
        (RDFResource(), ['Unpublished']),
        (RDFResource(rdf_type=umdaccess.Published), ['Published']),
    ]
)
def test_publication_status_facet(get_mock_resource, obj, expected_values):
    ctx = IndexerContext(
        repo=Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo'))),
        resource=get_mock_resource('/foo', obj),
        model_class=obj.__class__,
        doc={},
        config={},
    )
    faceter = PublicationStatusFacet(ctx)
    assert faceter.get_values() == expected_values


@pytest.mark.parametrize(
    ('obj', 'expected_values'),
    [
        (RDFResource(), ['Visible']),
        (RDFResource(rdf_type=umdaccess.Hidden), ['Hidden']),
    ]
)
def test_visibility_facet(get_mock_resource, obj, expected_values):
    ctx = IndexerContext(
        repo=Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo'))),
        resource=get_mock_resource('/foo', obj),
        model_class=obj.__class__,
        doc={},
        config={},
    )
    faceter = VisibilityFacet(ctx)
    assert faceter.get_values() == expected_values


def test_admin_set_facet(get_mock_resource):
    obj = PCDMObject(member_of=URIRef('http://example.com/collection'))
    collection = AdminSet(uri=URIRef('http://example.com/collection'), title=Literal('Test Admin Set'))
    mock_collection = MagicMock(spec=RepositoryResource)
    mock_collection.read.return_value = mock_collection
    mock_collection.describe.return_value = collection
    mock_repo = MagicMock(spec=Repository)
    mock_repo.__getitem__.return_value = mock_collection
    ctx = IndexerContext(
        repo=mock_repo,
        resource=get_mock_resource('/foo', obj),
        model_class=obj.__class__,
        doc={},
        config={},
    )
    faceter = AdminSetFacet(ctx)
    assert faceter.get_values() == ['Test Admin Set']


@pytest.mark.parametrize(
    ('binary_resource', 'expected_values'),
    [
        (True, ['Has OCR']),
        (False, None),
    ]
)
def test_ocr_facet(get_mock_resource, binary_resource, expected_values):
    obj = ContentModeledResource()
    mock_resource = get_mock_resource('/foo', obj, resource_class=PCDMObjectResource)
    mock_resource.get_members.return_value = []
    mock_resource.convert_to.return_value = mock_resource

    if binary_resource:
        mock_resource.get_file.return_value = 'Fake Binary Resource just needs to not be None'
    else:
        mock_resource.get_file.return_value = None

    ctx = IndexerContext(
        repo=Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo'))),
        resource=mock_resource,
        model_class=obj.__class__,
        doc={},
        config={},
    )

    faceter = OCRFacet(ctx)
    assert faceter.get_values() == expected_values


def test_presentation_set_attribute_error(get_mock_resource):
    obj = RDFResource()
    ctx = IndexerContext(
        repo=Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo'))),
        resource=get_mock_resource('/foo', obj),
        model_class=obj.__class__,
        doc={},
        config={},
    )
    faceter = PresentationSetFacet(ctx)
    assert faceter.get_values() is None


@pytest.mark.parametrize(
    ('description', 'expected_value'),
    [
        (Literal('Censorship Information: CCD No.: 2223; CCD Action: Yes (deletion); Price: 6 yen'), ['Yes']),
        (Literal('Censorship Information: CCD No.: 2223; Price: 6 yen'), ['No']),
        (Literal('Description not about Censorship'), None),
        (None, None)
    ]
)
def test_censorship_facet(get_mock_resource, description, expected_value):
    obj = Item(description=description) if description is not None else Item()

    ctx = IndexerContext(
        repo=Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo'))),
        resource=get_mock_resource('/foo', obj),
        model_class=obj.__class__,
        doc={},
        config={},
    )

    faceter = CensorshipFacet(ctx)
    assert faceter.get_values() == expected_value
