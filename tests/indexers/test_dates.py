from collections.abc import Iterable
from pathlib import Path

import pytest
from edtf import EDTFParseException, parse_edtf
from markdown_to_data import Markdown

from solrizer.indexers.dates import UnsupportedEDTFValue, date_fields, solr_date, get_precision, range_size

DOCS_DIR = Path(__file__).parents[2] / 'docs'


def get_values(params: dict[str, str | int | None]) -> list[str | int | bool | None]:
    values = []
    for k, v in params.items():
        if k.endswith('?'):
            values.append(bool(v))
        elif isinstance(v, int):
            values.append(v)
        elif isinstance(v, str):
            values.append(v.removeprefix('`').removesuffix('`'))
        else:
            values.append(None)
    return values


def has_columns(table: dict[str, str], columns: Iterable[str]) -> bool:
    return all(c in table for c in columns)


def get_param_set_from_markdown(file: Path, columns: Iterable[str]) -> list[tuple[str, ...]]:
    md = Markdown(file.read_text())
    tables = [t['table'] for t in md.md_list if 'table' in t and has_columns(t['table'], columns)]
    param_set = []
    for table in tables:
        rows = list(zip(*(table[c] for c in columns)))
        data = list(dict(zip(columns, row)) for row in rows)
        for params in data:
            param_set.append(tuple(get_values(params)))
    return param_set


EDTF_TEST_STRINGS = get_param_set_from_markdown(
    file=(DOCS_DIR / 'EDTFtoDateRange.md'),
    columns=['EDTF', 'Solr DateRange'],
)

QUALIFIED_EDTF_TEST_STRINGS = get_param_set_from_markdown(
    file=(DOCS_DIR / 'EDTFtoDateRange.md'),
    columns=[
        'EDTF',
        'Solr DateRange',
        'Uncertain?',
        'Approximate?',
        'Uncertain and Approximate?',
        'Precision',
        'Range Size',
    ],
)

UNSUPPORTED_EDTF_STRINGS = [
    # LongYear
    'Y21000',
    'Y-18000',
    # ExponentialYear
    'Y1E5',
    'Y-2E6',
]

INVALID_EDTF_STRINGS = [
    'Y1999-12-31',
    'FAKE',
]

EDTF_PRECISIONS = get_param_set_from_markdown(
    file=(DOCS_DIR / 'EDTFtoDateRange.md'),
    columns=['EDTF', 'Precision'],
)


@pytest.mark.parametrize(
    ('edtf_value', 'expected_solr_value'),
    EDTF_TEST_STRINGS,
)
def test_solr_date(edtf_value, expected_solr_value):
    assert solr_date(edtf_value) == expected_solr_value


@pytest.mark.parametrize(
    ('edtf_value', 'expected_solr_value'),
    EDTF_TEST_STRINGS,
)
def test_date_fields(edtf_value, expected_solr_value, context_with_date):
    fields = date_fields(context_with_date(edtf_value))
    assert fields['date__dt'] == expected_solr_value


@pytest.mark.parametrize(
    (
        'edtf_value',
        'expected_solr_value',
        'is_uncertain',
        'is_approximate',
        'is_uncertain_and_approximate',
        'precision',
        'dt_range_size',
    ),
    QUALIFIED_EDTF_TEST_STRINGS,
)
def test_uncertain_and_or_approximate(
    edtf_value,
    expected_solr_value,
    is_uncertain,
    is_approximate,
    is_uncertain_and_approximate,
    precision,
    dt_range_size,
    context_with_date,
):
    expected_fields = {
        'date__dt': expected_solr_value,
        'date__dt_is_uncertain': is_uncertain,
        'date__dt_is_approximate': is_approximate,
        'date__dt_is_uncertain_and_approximate': is_uncertain_and_approximate,
        'date__dt_precision__int': precision,
        'date__dt_range_size__int': dt_range_size,
    }
    assert date_fields(context_with_date(edtf_value)) == expected_fields


@pytest.mark.parametrize(
    'edtf_value',
    UNSUPPORTED_EDTF_STRINGS,
)
def test_unsupported_edtf_solr_date(edtf_value):
    with pytest.raises(UnsupportedEDTFValue):
        solr_date(edtf_value)


@pytest.mark.parametrize(
    'edtf_value',
    UNSUPPORTED_EDTF_STRINGS,
)
def test_unsupported_edtf_date_fields(edtf_value, context_with_date, caplog):
    fields = date_fields(context_with_date(edtf_value))
    assert fields == {}
    assert f'Cannot convert "{edtf_value}"' in caplog.text


@pytest.mark.parametrize(
    'edtf_value',
    INVALID_EDTF_STRINGS,
)
def test_edtf_parse_exception_solr_date(edtf_value):
    with pytest.raises(EDTFParseException):
        solr_date(edtf_value)


@pytest.mark.parametrize(
    'edtf_value',
    INVALID_EDTF_STRINGS,
)
def test_edtf_parse_exception_solr_date(edtf_value, context_with_date, caplog):
    fields = date_fields(context_with_date(edtf_value))
    assert fields == {}
    assert f'Cannot parse "{edtf_value}"' in caplog.text


@pytest.mark.parametrize(
    'edtf_value',
    [
        # LongYear
        'Y21000',
        'Y-18000',
        # ExponentialYear
        'Y1E5',
        'Y-2E6',
        # EDTF parse errors
        'Y-12000/1982',
    ],
)
def test_unsupported_edtf_returns_nothing(edtf_value, context_with_date):
    fields = date_fields(context_with_date(edtf_value))
    assert 'date__dt' not in fields


@pytest.mark.parametrize(
    ('edtf_value', 'expected_precision'),
    EDTF_PRECISIONS,
)
def test_get_precision(edtf_value, expected_precision):
    assert get_precision(parse_edtf(edtf_value)) == expected_precision


@pytest.mark.parametrize(
    ('edtf_value', 'expected_size'),
    [
        ('1990', 365),
        ('1990-12', 31),
        ('1990-11', 30),
        ('1990-02', 28),
        ('1990-11-26', 1),
        ('1900/1999', 36524),
        # ignores time portion
        ('1990-11-26T09:34:21', 1),
        # 2000 was a leap year
        ('2000', 366),
        ('2000-02', 29),
    ]
)
def test_range_size(edtf_value, expected_size):
    assert range_size(parse_edtf(edtf_value)) == expected_size


@pytest.mark.parametrize(
    ('edtf_value', 'equivalent_range'),
    [
        # unbounded ranges are clipped to 0001-01-01 and 9999-12-31
        ('/2000', '0001-01-01/2000'),
        ('2000/', '2000/9999-12-31'),
    ]
)
def test_unbounded_range_size(edtf_value, equivalent_range):
    assert range_size(parse_edtf(edtf_value)) == range_size(parse_edtf(equivalent_range))


def test_negative_date_range_size_is_none():
    assert range_size(parse_edtf('-0009')) is None
