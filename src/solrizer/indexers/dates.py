"""
Indexer Name: **`dates`**

Indexer implementation function: `date_fields()`

Prerequisites: Must run **after** the [`content_model`](./content_model) indexer

Output field patterns:

| Field pattern                                     | Python Type | Solr Type      |
|---------------------------------------------------|-------------|----------------|
| `object__{attr}__dt`                              | `str`       | datetime range |
| `object__{attr}__dt_is_uncertain`                 | `bool`      | boolean        |
| `object__{attr}__dt_is_approximate`               | `bool`      | boolean        |
| `object__{attr}__dt_is_uncertain_and_approximate` | `bool`      | boolean        |
| `object__{attr}__dt_precision__int`               | `int`       | integer        |
| `object__{attr}__dt_range_size__int`              | `int`       | integer        |
| `object__{attr}__millennium__facet`               | `str`       | string         |
| `object__{attr}__century__facet`                  | `str`       | string         |
| `object__{attr}__decade__facet`                   | `str`       | string         |
| `object__{attr}__year__facet`                     | `str`       | string         |
| `object__{attr}__month__facet`                    | `str`       | string         |
| `object__{attr}__day__facet`                      | `str`       | string         |

The facet field values are formatted in two parts: a "sort value" used to ensure that
a lexicographic sort of the values results in a chronological sort, and a "label" that
is intended to be displayed via any UIs that consume these fields.

| Facet level | Sort value pattern | Label pattern                    | Example sort value | Example label              |
|-------------|--------------------|----------------------------------|--------------------|----------------------------|
| millennium  | `YXXX`             | (Y + 1)th Millennium (Y000-Y999) | `1XXX`             | 2nd Millennium (1000-1999) |
| century     | `YYXX`             | (YY + 1)th Century (YY00-YY99)   | `19XX`             | 20th Century (1900-1999)   |
| decade      | `YYYX`             | YYY0s (YYY0-YYY9)                | `194X`             | 1940s (1940-1949)          |
| year        | `YYYY`             | YYYY                             | `1944`             | 1944                       |
| month       | `MM`               | Month                            | `06`               | June                       |
| day         | `DD`               | D                                | `06`               | 6                          |

The sort value and label are combined using a pipe character (`|`) and added to the
Solr document as a single string (e.g., `19XX|20th Century (1900-1999)`).

For any level, if the date metadata does not map to a definite value for that level,
the string "Unspecified" is used for both the facet sort value and label.
"""  # noqa: E501

import logging
import re
from calendar import month_name
from datetime import datetime, date
from typing import NamedTuple

from edtf import (parse_edtf, Date, UnspecifiedIntervalSection, EDTFObject, UncertainOrApproximate, Interval,
                  Level2Interval, Season, Unspecified, ExponentialYear, LongYear, EDTFParseException, DateAndTime,
                  PartialUncertainOrApproximate, OneOfASet, Consecutives, struct_time_to_date)
from humanize import ordinal

from solrizer.indexers import IndexerContext, SolrFields
from solrizer.indexers.utils import solr_datetime

logger = logging.getLogger(__name__)

YMD_STRING = '{0:04d}-{1:02d}-{2:02d}'
"""Formatting string used by `strict_range()` to generate `YYYY-MM-DD` strings."""

PRECISION_VALUES = {
    'day': 6,
    'month': 5,
    'year': 4,
    'decade': 3,
    'century': 2,
    'millennium': 1,
    # the python-edtf module spells "millennium" with only one "n"
    'millenium': 1,
}
"""Mapping of precision-level names to numerical values for sorting."""


def date_fields(ctx: IndexerContext) -> SolrFields:
    """For any EDTF field in the index document (i.e., one whose name ends
    with `__edtf`) creates a corresponding `__dt` field with a value that
    is parseable by Solr as a date or date range. Also, populates up to
    eleven other fields:

    * three boolean flag fields with the suffixes `__dt_is_uncertain`,
      `__dt_is_approximate`,and `__dt_is_uncertain_and_approximate` that
      indicate whether the EDTF string had the markers for uncertainty (`?`),
      approximation (`~`), or both (`%`).
    * an integer field with the suffix `__dt_precision__int` to capture the
      precision of the original EDTF date
    * an integer field with the suffix `__dt_range_size__int` the contains
      the number of days covered by the EDTF date; if for any reason it
      cannot calculate this value from the EDTF date, it emits a warning and
      sets this field to `None` (see `range_size` for more details)
    * for singular dates, six facet fields to support "drill-down" dependent
      faceting from low (millennium) to high (day) precision

    Emits a warning and skips any EDTF fields that cannot be represented
    as Solr dates (e.g., exponential years, years with more than four digits),
    or that cannot even be parsed as EDTF strings."""

    # EDTF fields
    for edtf_name in filter(lambda n: n.endswith('__edtf'), ctx.doc.keys()):
        edtf_string = ctx.doc[edtf_name]
        name = edtf_name.replace('__edtf', '')
        try:
            edtf: EDTFObject = parse_edtf(str(edtf_string))
            fields = {
                name + '__dt': solr_date(edtf),
                name + '__dt_is_uncertain': edtf.is_uncertain,
                name + '__dt_is_approximate': edtf.is_approximate,
                name + '__dt_is_uncertain_and_approximate': edtf.is_uncertain_and_approximate,
                name + '__dt_precision__int': get_precision(edtf),
                name + '__dt_range_size__int': range_size(edtf),
            }
            if facetable_date := _get_facetable_date(edtf):
                date_facets = EDTFFacets(facetable_date).get_facets(prefix=f'{name}__', suffix='__facet')
                fields.update(date_facets)

            return fields
        except UnsupportedEDTFValue as e:
            logger.warning(f'Cannot convert "{edtf_string}" in field {edtf_name} to a Solr date: {e.reason}')
        except EDTFParseException:
            logger.warning(f'Cannot parse "{edtf_string}" in field {edtf_name} as an EDTF string')
    else:
        return {}


def strict_range(edtf: EDTFObject) -> str:
    """Format the given EDTF date as a Solr date range, using the strict
    upper and lower bounds of the EDTF date."""

    begin = YMD_STRING.format(*edtf.lower_strict()[:3])
    end = YMD_STRING.format(*edtf.upper_strict()[:3])
    return f'[{begin} TO {end}]'


def range_size(edtf: EDTFObject) -> int | None:
    """Get the number of days between the upper and lower bounds of the given
    EDTF date. If the EDTF expression is unbounded on either side, this function
    sets the begin or end date to for the purposes of its calculation to
    0001-01-01 or 9999-12-31, respectively.

    If the EDTF expression falls outside the range year 1 to year 9999 (i.e.,
    it is not expressible via a `time.struct_time` object), this function returns
    `None`."""

    try:
        if isinstance(edtf, Interval) and isinstance(edtf.lower, UnspecifiedIntervalSection):
            begin = date(1, 1, 1)
        else:
            begin = struct_time_to_date(edtf.lower_strict())

        if isinstance(edtf, Interval) and isinstance(edtf.upper, UnspecifiedIntervalSection):
            end = date(9999, 12, 31)
        else:
            end = struct_time_to_date(edtf.upper_strict())
    except ValueError as e:
        logger.warning(f'Unable to calculate date range size for EDTF expression "{edtf}": {e}')
        return None

    return (end - begin).days + 1


def solr_date(edtf_value: str | EDTFObject, partial_ua_method: str = 'lower_strict') -> str:
    """Convert an EDTF string (or an already parsed `EDTFObject`) into
    a date or date range string valid for Solr.

    Raises an `UnsupportedEDTFValue` exception if the `edtf_value` cannot
    be parsed or cannot be represented as a Solr datetime range."""

    if isinstance(edtf_value, EDTFObject):
        edtf = edtf_value
    else:
        edtf = parse_edtf(edtf_value)

    match edtf:
        case ExponentialYear():
            if abs(int(edtf.exponent)) > 3:
                raise UnsupportedEDTFValue(
                    edtf=edtf,
                    reason='Solr does not support years outside the range -9999 to 9999',
                )
            else:
                return strict_range(edtf)
        case LongYear():
            raise UnsupportedEDTFValue(
                edtf=edtf,
                reason='Solr does not support years outside the range -9999 to 9999',
            )
        case Season() | Unspecified():
            return strict_range(edtf)
        case UnspecifiedIntervalSection():
            return '*'
        case Level2Interval():
            lower = edtf.lower
            upper = edtf.upper
            return f'[{solr_date(lower, 'lower_strict')} TO {solr_date(upper, 'upper_strict')}]'
        case Interval():
            lower = edtf.lower
            upper = edtf.upper
            return f'[{solr_date(lower)} TO {solr_date(upper)}]'
        case UncertainOrApproximate():
            return str(edtf.date)
        case PartialUncertainOrApproximate():
            time_data = getattr(edtf, partial_ua_method)()
            return str(datetime(*time_data[:7]).date())
        case Date():
            return str(edtf)
        case DateAndTime():
            return solr_datetime(str(edtf))
        case _:
            raise UnsupportedEDTFValue(edtf=edtf)


def get_precision(edtf: EDTFObject) -> int | None:
    """Determine the precision of the given EDTF object and return the
    equivalent numerical value taken from `PRECISION_VALUES`."""
    match edtf:
        case UncertainOrApproximate():
            return get_precision(edtf.date)
        case OneOfASet():
            precisions = []
            for obj in edtf.objects:
                precisions.extend(_get_upper_and_lower_precisions(obj))
            return min(precisions) if precisions else None
        case Interval():
            precisions = _get_upper_and_lower_precisions(edtf)
            return min(precisions) if precisions else None
        case Season():
            # TODO: what should season precision be?
            return None
        case Date() | UnspecifiedIntervalSection():
            return PRECISION_VALUES[edtf.precision]
        case _:
            return None


def _get_upper_and_lower_precisions(edtf: Interval | Consecutives):
    precisions = [
        get_precision(edtf.lower),
        get_precision(edtf.upper),
    ]
    return [p for p in precisions if p is not None]


def _get_facetable_date(edtf: EDTFObject) -> Date | None:
    match edtf:
        case Date():
            return edtf
        case DateAndTime():
            return edtf.date
        case _:
            return None


class EDTFFacetValue(NamedTuple):
    """Pairing of the sort value and label for a given date facet value.
    Stringifies to `{sort_value}|{label}`."""
    sort_value: str
    """Value used to ensure proper lexicographic sorting (e.g., `19XX`)."""
    label: str
    """Human-friendly label for use by UIs (e.g., `20th Century (1900-1999)`)."""

    def __str__(self):
        return f'{self.sort_value}|{self.label}'


SPECIFIED_MILLENNIUM = re.compile(r'\d\d\d[\dX]|\d\d[\dX]X|\d[\dX]XX')
SPECIFIED_CENTURY = re.compile(r'\d\d\d[\dX]|\d\d[\dX]X')
SPECIFIED_DECADE = re.compile(r'\d\d\d[\dX]')
SPECIFIED_YEAR = re.compile(r'\d\d\d')
UNSPECIFIED_VALUE = EDTFFacetValue('Unspecified', 'Unspecified')


class EDTFFacets:
    def __init__(self, edtf_value: Date):
        self._date = edtf_value
        self._year = self._date.year

    @property
    def millennium(self) -> EDTFFacetValue:
        if self._year and SPECIFIED_MILLENNIUM.match(self._year):
            y = self._year[0:1]
            millennium = ordinal(int(y) + 1)
            return EDTFFacetValue(
                f'{y}XXX',
                f'{millennium} Millennium ({y}000-{y}999)',
            )
        else:
            return UNSPECIFIED_VALUE

    @property
    def century(self) -> EDTFFacetValue:
        if self._year and SPECIFIED_CENTURY.match(self._year):
            yy = self._year[0:2]
            century = ordinal(int(yy) + 1)
            return EDTFFacetValue(
                f'{yy}XX',
                f'{century} Century ({yy}00-{yy}99)',
            )
        else:
            return UNSPECIFIED_VALUE

    @property
    def decade(self) -> EDTFFacetValue:
        if self._year and SPECIFIED_DECADE.match(self._year):
            yyy = self._year[0:3]
            decade = f'{yyy}0s'.removeprefix('0').removeprefix('0')
            return EDTFFacetValue(
                f'{yyy}X',
                f'{decade} ({yyy}0-{yyy}9)',
            )
        else:
            return UNSPECIFIED_VALUE

    @property
    def year(self) -> EDTFFacetValue:
        if self._year and SPECIFIED_YEAR.match(self._year):
            return EDTFFacetValue(
                self._year,
                self._year.lstrip('0'),
            )
        else:
            return UNSPECIFIED_VALUE

    @property
    def month(self) -> EDTFFacetValue:
        if not isinstance(self._date, Season) and self._date.month and 'X' not in self._date.month:
            return EDTFFacetValue(
                str(self._date.month),
                month_name[int(str(self._date.month))],
            )
        else:
            return UNSPECIFIED_VALUE

    @property
    def day(self) -> EDTFFacetValue:
        if self._date.day and 'X' not in self._date.day:
            return EDTFFacetValue(
                str(self._date.day),
                str(self._date.day).lstrip('0'),
            )
        else:
            return UNSPECIFIED_VALUE

    def get_facets(self, prefix: str = '', suffix: str = ''):
        return {
            f'{prefix}millennium{suffix}': str(self.millennium),
            f'{prefix}century{suffix}': str(self.century),
            f'{prefix}decade{suffix}': str(self.decade),
            f'{prefix}year{suffix}': str(self.year),
            f'{prefix}month{suffix}': str(self.month),
            f'{prefix}day{suffix}': str(self.day),
        }


class UnsupportedEDTFValue(ValueError):
    """Raised to indicate this is a valid EDTF string, but one that is not
    translatable into a Solr date or date range."""

    def __init__(self, *args, edtf: EDTFObject, reason: str = 'Solr does not support this EDTF value'):
        super().__init__(*args)
        self.edtf: EDTFObject = edtf
        """The unsupported EDTF object"""
        self.reason: str = reason
        """The reason this `edtf` cannot be represented in Solr"""
