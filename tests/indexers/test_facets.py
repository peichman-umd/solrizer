import pytest
from plastron.client import Client, Endpoint
from plastron.models import letter, umd, ContentModeledResource
from plastron.models.letter import Letter
from plastron.models.newspaper import Issue
from plastron.models.poster import Poster
from plastron.models.umd import Item
from plastron.repo import Repository
from plastron.repo.pcdm import PCDMObjectResource
from rdflib import Literal, URIRef

from solrizer.indexers import IndexerContext
from solrizer.indexers.facets import facet_fields


@pytest.mark.parametrize(
    ('obj', 'expected_fields'),
    [
        pytest.param(
            Item(
                archival_collection=URIRef('http://vocab.lib.umd.edu/collection#0051-MDHC'),
                contributor=umd.Agent(label=Literal('Agent 1')),
                creator=umd.Agent(label=Literal('Agent 2')),
                format=URIRef('http://vocab.lib.umd.edu/form#postcards'),
                language=[Literal('en'), Literal('de')],
                presentation_set=URIRef('http://vocab.lib.umd.edu/set#labor'),
                publisher=umd.Agent(label=Literal('Agent 3')),
                rights=URIRef('http://vocab.lib.umd.edu/rightsStatement#InC'),
                subject=[
                    umd.Subject(label=Literal('Vacation')),
                    umd.Subject(label=Literal('Beach')),
                ],
            ),
            {
                'archival_collection__facet': ['Maryland Conservation Council records'],
                'contributor__facet': ['Agent 1'],
                'creator__facet': ['Agent 2'],
                'resource_type__facet': ['Postcards'],
                'language__facet': ['English', 'German'],
                'presentation_set__facet': ['Labor'],
                'publication_status__facet': ['Unpublished'],
                'publisher__facet': ['Agent 3'],
                'rights__facet': ['In Copyright'],
                'subject__facet': ['Vacation', 'Beach'],
                'visibility__facet': ['Visible'],
            },
            id='Item',
        ),
        pytest.param(
            Letter(
                author=letter.Agent(label=Literal('Agent 2')),
                language=Literal('en'),
                part_of=letter.Collection(label=Literal('Foo')),
                place=[
                    letter.Place(label=Literal('Caprica')),
                ],
                presentation_set=URIRef('http://vocab.lib.umd.edu/set#labor'),
                rights=URIRef('http://rightsstatements.org/vocab/InC/1.0/'),
                subject=[
                    letter.Concept(label=Literal('Vacation')),
                    letter.Concept(label=Literal('Beach')),
                ],
                type=Literal('Letters'),
            ),
            {
                'creator__facet': ['Agent 2'],
                'language__facet': ['English'],
                'archival_collection__facet': ['Foo'],
                'location__facet': ['Caprica'],
                'presentation_set__facet': ['Labor'],
                'publication_status__facet': ['Unpublished'],
                'rights__facet': ['In Copyright'],
                'subject__facet': ['Vacation', 'Beach'],
                'resource_type__facet': ['Letters'],
                'visibility__facet': ['Visible'],
            },
            id='Letter',
        ),
        pytest.param(
            Poster(
                format=Literal('Newspaper, 70 cm. x 120 cm.'),
                language=Literal('English'),
                location=Literal('Tokyo'),
                part_of=Literal('Foo'),
                presentation_set=URIRef('http://vocab.lib.umd.edu/set#labor'),
                publisher=Literal('Agent 3'),
                rights=URIRef('http://rightsstatements.org/vocab/InC/1.0/'),
                subject=[Literal('Vacation'), Literal('Beach')],
            ),
            {
                'resource_type__facet': ['Newspaper'],
                'language__facet': ['English'],
                'location__facet': ['Tokyo'],
                'archival_collection__facet': ['Foo'],
                'presentation_set__facet': ['Labor'],
                'publication_status__facet': ['Unpublished'],
                'publisher__facet': ['Agent 3'],
                'rights__facet': ['In Copyright'],
                'subject__facet': ['Vacation', 'Beach'],
                'visibility__facet': ['Visible'],
            },
            id='Poster',
        ),
        pytest.param(
            Issue(
                title=Literal('The diamondback (College Park, Md.), 1995-04-01'),
                presentation_set=URIRef('http://vocab.lib.umd.edu/set#labor'),
            ),
            {
                'presentation_set__facet': ['Labor'],
                'publication_status__facet': ['Unpublished'],
                'publication_title__facet': ['The Diamondback'],
                'resource_type__facet': ['Newspapers'],
                'visibility__facet': ['Visible'],
            },
            id='Issue',
        ),
    ],
)
def test_facet_fields(obj: ContentModeledResource, expected_fields, mock_vocabularies, get_mock_resource):

    mock_resource = get_mock_resource('/foo', obj, resource_class=PCDMObjectResource)
    mock_resource.get_members.return_value = []
    mock_resource.convert_to.return_value = mock_resource
    mock_resource.get_file.return_value = None

    ctx = IndexerContext(
        repo=Repository(client=Client(endpoint=Endpoint('http://example.com/fcrepo'))),
        resource=mock_resource,
        model_class=obj.__class__,
        doc={},
        config={},
    )
    assert facet_fields(ctx) == expected_fields
