"""
Indexer Name: **`content_model`**

Indexer implementation function: `content_model_fields()`

Prerequisites: None

Output field patterns:

| Field pattern                 | Python Type            | Solr Type                   |
|-------------------------------|------------------------|-----------------------------|
| `{model}__{attr}__int`        | `int`                  | integer                     |
| `{model}__{attr}__id`         | `str`                  | string                      |
| `{model}__{attr}__dt`         | `datetime`             | datetime range              |
| `{model}__{attr}__edtf`       | `str`                  | string                      |
| `{model}__{attr}__txt`        | `str`                  | tokenized text              |
| `{model}__{attr}__txt_{lang}` | `str`                  | tokenized text for `{lang}` |
| `{model}__{attr}__uri`        | `str`                  | string                      |
| `{model}__{attr}__curie`      | `str`                  | string                      |
| `{model}__{attr}`             | `list[dict[str, ...]]` | nested document             |
"""

import logging
from typing import Iterable, Callable, Iterator

from langcodes import standardize_tag, LanguageTagError
from plastron.models.authorities import VocabularyTerm
from plastron.namespaces import xsd, umdtype, namespace_manager
from plastron.rdfmapping.properties import RDFDataProperty, RDFObjectProperty, RDFProperty
from plastron.rdfmapping.resources import RDFResource, RDFResourceBase
from plastron.repo import Repository
from rdflib import Literal, URIRef

from solrizer.indexers import SolrFields, IndexerContext, IndexerError

logger = logging.getLogger(__name__)

FIELD_ARGUMENTS_BY_DATATYPE = {
    # integer types
    xsd.int: {'suffix': '__int', 'converter': int},
    xsd.integer: {'suffix': '__int', 'converter': int},
    xsd.long: {'suffix': '__int', 'converter': int},
    # datetime type
    xsd.dateTime: {'suffix': '__dt'},
    # identifier types
    umdtype.accessionNumber: {'suffix': '__id'},
    umdtype.handle: {'suffix': '__id'},
}
"""Field mappings for RDF literals with particular datatypes."""

FIELD_ARGUMENTS_BY_ATTR_NAME = {
    'date': {'suffix': '__edtf'},
    'identifier': {'suffix': '__id'},
}
"""Field mappings for fields with particular property names."""


def content_model_fields(ctx: IndexerContext) -> SolrFields:
    """Indexer function that adds fields generated from the indexed
    resource's content model. Registered as the entry point
    *content_model* in the `solrizer_indexers` entry point group."""
    model_name = ctx.model_class.__name__
    prefix = model_name.lower() + '__'
    return {
        'content_model_name__str': model_name,
        'content_model_prefix__str': prefix,
        **get_model_fields(ctx.obj, repo=ctx.repo, prefix=prefix),
    }


def get_model_fields(obj: RDFResourceBase, repo: Repository, prefix: str = '') -> SolrFields:
    """Iterates over the RDF properties of `obj`, and creates a dictionary of Solr field
    names to values."""
    logger.info(f'Converting {obj.uri}')
    fields = {}
    for prop in obj.rdf_properties():
        if len(prop) == 0:
            # skip properties with no values
            logger.debug(f'Skipping empty property {prop.attr_name}')
            continue
        if isinstance(prop, RDFDataProperty):
            fields.update(get_data_fields(prop, prefix))
        elif isinstance(prop, RDFObjectProperty):
            fields.update(get_object_fields(prop, repo, prefix))

    return fields


def get_linked_objects(prop: RDFObjectProperty, repo: Repository) -> Iterator[RDFResource]:
    """Iterate over the URIs in `prop.values`, retrieving the resource at
    each URI and returning it described using the `prop.object_class`."""
    for uri in prop.values:
        yield repo[uri].read().describe(prop.object_class)


def get_child_documents(prefix: str, objects: Iterable[RDFResource], repo: Repository) -> list[SolrFields]:
    """Returns a list containing an index document for each resource in `objects`."""
    return [{'id': str(o.uri), **get_model_fields(o, repo=repo, prefix=prefix)} for o in objects]


def language_suffix(language: str | None) -> str:
    """Normalizes the `language` string by:

    * standardizing using the `langcodes.standardize_tag()` function;
      in particular, this changes 3-letter ISO 639 codes to their
      2-letter equivalents (for example, "eng" becomes "en")
    * converting to all lower case
    * changing all "-" to "_"

    Returns the normalized value, prepended with "_". If `language`
    is `None`, returns an empty string instead.

    ```pycon
    >>> language_suffix('en')
    '_en'
    >>> language_suffix('en-US')
    '_en_us'
    >>> language_suffix('ja-Latn')
    '_ja_latn'
    >>> language_suffix('eng')
    '_en'
    >>> language_suffix('jpn-LATN')
    '_ja-latn'
    >>> language_suffix(None)
    ''
    ```
    """
    if language is not None:
        try:
            return '_' + standardize_tag(language).lower().replace('-', '_')
        except LanguageTagError as e:
            logger.error(str(e))
            raise IndexerError(f'Unable to determine language suffix from "{language}"')
    else:
        return ''


def get_data_fields(prop: RDFDataProperty, prefix: str = '') -> SolrFields:
    """Get the dictionary of field key(s) and value(s) for the given data
    property using `get_field()`. All keys are prepended with the given
    `prefix`.

    If the property has a datatype found in `FIELD_ARGUMENTS_BY_DATATYPE`,
    the parameters for `get_field()` are taken from there. Similarly, if
    the property has a name found in `FIELD_ARGUMENTS_BY_ATTR_NAME`, arguments
    are taken from there. Otherwise, the property is treated as text. For
    unique language among the property's values, it creates a key from the
    property name followed by "__txt" and then followed by a language suffix,
    as determined by `language_suffix()`.
    """
    if prop.datatype in FIELD_ARGUMENTS_BY_DATATYPE:
        # special handling per datatype
        return get_field(prop, prefix, **FIELD_ARGUMENTS_BY_DATATYPE[prop.datatype])
    else:
        # special handling per property name
        if prop.attr_name in FIELD_ARGUMENTS_BY_ATTR_NAME:
            return get_field(prop, prefix, **FIELD_ARGUMENTS_BY_ATTR_NAME[prop.attr_name])
        else:
            # everything else is treated as text
            fields = {}
            for language in prop.languages:
                fields.update(get_field(
                    prop=prop,
                    prefix=prefix,
                    suffix='__txt' + language_suffix(language),
                    value_filter=lambda v: v.language == language,
                ))
            return fields


def get_object_fields(prop: RDFObjectProperty, repo: Repository, prefix: str = '') -> SolrFields:
    """Get the dictionary of field key(s) and value(s) for the given object
    property using `get_field()`. All keys are prepended with the given
    `prefix`.

    All properties get fields for their URI and CURIE values, suffixed as
    "__uri" and "__curie", respectively.

    If a property's values are from a controlled vocabulary, additional
    fields are populated using the `VocabularyTerm` model. These fields
    appear as siblings to the other top level fields.

    If a property's values are the URIs of embedded (i.e., "hash URI")
    or linked (i.e., child resources also in the repository) resources, adds
    a field for that property whose value is a list of the indexing documents
    for those embedded resources. This structure will establish a set of
    nested documents once it is added to Solr.
    """
    fields = {}
    fields.update(get_field(prop, prefix, '__uri'))
    fields.update(get_field(prop, prefix, '__curie', converter=shorten_uri))
    if prop.object_class is VocabularyTerm:
        if prop.object is not None:
            # add vocabulary fields
            fields.update(get_model_fields(prop.object, repo=repo, prefix=prefix + prop.attr_name + '__'))
    elif prop.embedded:
        fields[prefix + prop.attr_name] = get_child_documents(
            prefix=prop.object_class.__name__.lower() + '__',
            objects=prop.objects,
            repo=repo,
        )
    elif prop.object_class is not None:
        # linked object
        fields[prefix + prop.attr_name] = get_child_documents(
            prefix=prop.object_class.__name__.lower() + '__',
            objects=get_linked_objects(prop, repo),
            repo=repo,
        )
    return fields


def get_field(
    prop: RDFProperty,
    prefix: str = '',
    suffix: str = '__str',
    converter: Callable[[Literal | URIRef], str | int] = str,
    value_filter: Callable[[Literal | URIRef], bool] = lambda v: True,
) -> SolrFields:
    """Convert a property to a `{field_name: value(s)}` format dictionary.

    If `value_filter` is given, only those values that pass the value filter
    (i.e., return `True`) are included.

    If `converter` is given, it is applied to the included values. Should
    return a `str` or `int`. Default is `str()`."""
    name = prefix + prop.attr_name + suffix
    values = [converter(v) for v in prop.values if value_filter(v)]
    if prop.repeatable:
        return {name + 's': values}
    else:
        return {name: values[0]}


def shorten_uri(uri: str) -> str | None:
    """Attempt to shorten `uri` into a CURIE with a known prefix. If no
    such prefix is found, returns the full `uri` string. If `uri` is
    `None`, returns `None`."""
    if uri is None:
        return None
    try:
        return namespace_manager.curie(uri, generate=False)
    except (KeyError, ValueError):
        return str(uri)
