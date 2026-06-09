import pytest
from edtf import parse_edtf

from solrizer.indexers.dates import EDTFFacets, date_fields

DATE_FACET_TEST_VALUES = [
    ('2026-04-07', {
        'millennium': '2XXX|3rd Millennium (2000-2999)',
        'century': '20XX|21st Century (2000-2099)',
        'decade': '202X|2020s (2020-2029)',
        'year': '2026|2026',
        'month': '04|April',
        'day': '07|7',
    }),
    ('1944-06', {
        'millennium': '1XXX|2nd Millennium (1000-1999)',
        'century': '19XX|20th Century (1900-1999)',
        'decade': '194X|1940s (1940-1949)',
        'year': '1944|1944',
        'month': '06|June',
        'day': 'Unspecified|Unspecified',
    }),
    ('1919', {
        'millennium': '1XXX|2nd Millennium (1000-1999)',
        'century': '19XX|20th Century (1900-1999)',
        'decade': '191X|1910s (1910-1919)',
        'year': '1919|1919',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
    ('19XX', {
        'millennium': '1XXX|2nd Millennium (1000-1999)',
        'century': '19XX|20th Century (1900-1999)',
        'decade': 'Unspecified|Unspecified',
        'year': 'Unspecified|Unspecified',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
    ('2XXX', {
        'millennium': '2XXX|3rd Millennium (2000-2999)',
        'century': 'Unspecified|Unspecified',
        'decade': 'Unspecified|Unspecified',
        'year': 'Unspecified|Unspecified',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
    ('0891', {
        'millennium': '0XXX|1st Millennium (0000-0999)',
        'century': '08XX|9th Century (0800-0899)',
        'decade': '089X|890s (0890-0899)',
        'year': '0891|891',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
    ('0033', {
        'millennium': '0XXX|1st Millennium (0000-0999)',
        'century': '00XX|1st Century (0000-0099)',
        'decade': '003X|30s (0030-0039)',
        'year': '0033|33',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
    ('0002', {
        'millennium': '0XXX|1st Millennium (0000-0999)',
        'century': '00XX|1st Century (0000-0099)',
        'decade': '000X|00s (0000-0009)',
        'year': '0002|2',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
    ('1066', {
        'millennium': '1XXX|2nd Millennium (1000-1999)',
        'century': '10XX|11th Century (1000-1099)',
        'decade': '106X|1060s (1060-1069)',
        'year': '1066|1066',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
    ('1492', {
        'millennium': '1XXX|2nd Millennium (1000-1999)',
        'century': '14XX|15th Century (1400-1499)',
        'decade': '149X|1490s (1490-1499)',
        'year': '1492|1492',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
    ('1776', {
        'millennium': '1XXX|2nd Millennium (1000-1999)',
        'century': '17XX|18th Century (1700-1799)',
        'decade': '177X|1770s (1770-1779)',
        'year': '1776|1776',
        'month': 'Unspecified|Unspecified',
        'day': 'Unspecified|Unspecified',
    }),
]


@pytest.mark.parametrize(
    ('edtf_string', 'expected_facets'),
    DATE_FACET_TEST_VALUES,
)
def test_edtf_facets_class(edtf_string, expected_facets):
    assert EDTFFacets(parse_edtf(edtf_string)).get_facets() == expected_facets


@pytest.mark.parametrize(
    ('edtf_string', 'expected_facets'),
    DATE_FACET_TEST_VALUES,
)
def test_date_fields_facets(context_with_date, edtf_string, expected_facets):
    fields = date_fields(context_with_date(edtf_string))
    for key, value in expected_facets.items():
        assert fields[f'date__{key}__facet'] == value
