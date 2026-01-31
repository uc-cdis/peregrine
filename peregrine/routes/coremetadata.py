import html
import json

from cdiserrors import InternalError, NotFoundError
from cdislogging import get_logger
from fastapi import APIRouter, Depends, Header, Request
from peregrine.fast_api import get_app_context, get_request_state
from peregrine.resources.submission import do_graphql_query


CITATION_FIELDS = ["creator", "updated_datetime", "title", "publisher", "object_id"]

METADATA_QUERY_FIELDS = [
    "type",
    "file_name",
    "data_format",
    "file_size",
    "project_id",
    "object_id",
    "updated_datetime",
    "md5sum",
]

CORE_METADATA_QUERY_FIELDS = [
    "title",
    "description",
    "creator",
    "contributor",
    "coverage",
    "language",
    "publisher",
    "rights",
    "source",
    "subject",
]

router = APIRouter()
logger = get_logger(__name__, log_level="info")


@router.get("/<path:object_id>")
def get_core_metadata(
    object_id: str,
    app_ctx=Depends(get_app_context),
    request_state=Depends(get_request_state),
    accept: str | None = Header(None),
):
    """
    Get core metadata from an object_id
    ---
    tags:
      - core_metadata
    produces:
      - application/json
      - x-bibtex
      - application/vnd.schemaorg.ld+json
    parameters:
      - name: object_id
        in: path
        type: string
        required: true
      - name: Accept
        in: header
        type: string
        enum: [application/json (default), x-bibtex, application/vnd.schemaorg.ld+json]
      - name: app_ctx
        Application-level context injected via dependency.
        Provides access to shared resources such as the database,
        configuration, logger, and GraphQL schema.
      - name: request_state
        Request-scoped state injected via dependency.
        Used to store and share per-request data (for example,
        computed access-controlled project lists).
    responses:
      200:
        description: OK
        examples:
            application/json:
                '{"file_name": "my-file.txt", "data_format": "TXT", "file_size": 10, "object_id": "123"}'
            x-bibtex:
                '@misc {123, file_name = "my-file.txt", data_format = "TXT", file_size = "10", object_id = "123"}'
            application/vnd.schemaorg.ld+json:
                '{"@context": "http://schema.org", "@type": "Dataset", "@id": "https://dataguids.org/index/123", "identifier": [{"@type": "PropertyValue", "propertyID": "dataguid", "value": "123"}, {"@type": "PropertyValue", "propertyID": "md5", "value": "bc575394b5565a1d3fa20abe2b132896"}], "publisher": {"@type": "Organization", "name": "my-org"}, "author": {"name": "my-author"}, "description": "my-description", "additionalType": "submitted_aligned_reads", "name": "my-file.txt", "datePublished": "2019-01-24T19:40:02.537991+00:00"}'
      401:
        description: Authentication error
      404:
        description: No core metadata was found for this object_id
    """
    object_id = html.escape(object_id)
    logger.info("Getting metadata for object_id: {}".format(object_id))

    if accept == "x-bibtex":
        return get_bibtex_metadata(object_id, app_ctx, request_state)
    elif accept == "application/vnd.schemaorg.ld+json":
        return get_schemaorg_json_metadata(object_id, app_ctx, request_state)
    else:  # accept == "application/json" or no accept header
        return get_json_metadata(object_id, app_ctx, request_state)


def get_schemaorg_json_metadata(object_id, app_ctx, request_state):
    """
    Get core metadata as a Schema.org JSON from an object_id.
    """
    try:
        metadata = get_metadata_dict(object_id, app_ctx, request_state)
        schemaorg = {
            "@context": "http://schema.org",
            "@type": "Dataset",
            "@id": "https://dataguids.org/index/" + object_id,
            "identifier": [
                {
                    "@type": "PropertyValue",
                    "propertyID": "dataguid",
                    "value": object_id,
                },
                {
                    "@type": "PropertyValue",
                    "propertyID": "md5",
                    "value": metadata["md5sum"],
                },
            ],
        }
        if "publisher" in metadata:
            schemaorg["publisher"] = {
                "@type": "Organization",
                "name": metadata["publisher"],
            }
        if "creator" in metadata:
            schemaorg["author"] = {"name": metadata["creator"]}
        if "description" in metadata:
            schemaorg["description"] = metadata["description"]
        if "type" in metadata:
            schemaorg["additionalType"] = metadata["type"]
        if "file_name" in metadata:
            schemaorg["name"] = metadata["file_name"]
        if "updated_datetime" in metadata:
            schemaorg["datePublished"] = metadata["updated_datetime"]

        # "schemaVersion": "http://datacite.org/schema/kernel-4",

        return json.dumps(schemaorg)  # translate dictionary to json
    except InternalError as e:
        return e.message, e.code


def get_json_metadata(object_id, app_ctx, request_state):
    """
    Get core metadata as JSON from an object_id.
    """
    try:
        metadata = get_metadata_dict(object_id, app_ctx, request_state)
        return json.dumps(metadata)  # translate dictionary to json
    except InternalError as e:
        return e.message, e.code


def get_bibtex_metadata(object_id, app_ctx, request_state):
    """
    Get core metadata as BibTeX from an object_id.
    """
    try:
        metadata = get_metadata_dict(object_id, app_ctx, request_state)
        return translate_dict_to_bibtex(metadata)
    except InternalError as e:
        return e.message, e.code


def get_metadata_dict(object_id, app_ctx, request_state):
    """
    Create a dictionary containing the metadata for a given object_id.
    """
    response = request_metadata(object_id, app_ctx, request_state)  # graphql query
    metadata = flatten_dict(response)

    if any(field in metadata for field in CITATION_FIELDS):
        metadata["citation"] = generate_citation(metadata)

    return remove_unused_fields(metadata)


def translate_dict_to_bibtex(d):
    """
    Translate a dictionary to a BibTeX string.
    """
    items = ['{} = "{}"'.format(k, v) for k, v in d.items()]
    bibtex_items = ", ".join(items)
    bibtex_str = "@misc {" + d["object_id"] + ", " + bibtex_items + "}"
    return bibtex_str


def flatten_dict(d):
    """
    Flatten a dictionary that contains core metadata.
    """
    flat_d = {}
    try:
        data_type = list(d.keys())[0]
        for k, v in d[data_type][0].items():
            if k == "core_metadata_collections":
                if v:
                    # object_id is unique so the list should only contain one item
                    flat_d.update(v[0])
            else:
                flat_d[k] = v
    except (AttributeError, IndexError):
        error = "Core metadata not available for this file"
        if "errors" in d:
            error += ": " + d["errors"][0]
        logger.error(error)
        raise NotFoundError(error)
    return flat_d


def generate_citation(metadata_dict):
    """
    Generate a citation from the other metadata.
    """
    string = ""
    if metadata_dict.get("creator"):
        string += f'{metadata_dict["creator"]}, '
    if metadata_dict.get("updated_datetime"):
        year = metadata_dict.pop("updated_datetime").split("-")[0]
        string += f"{year}: "
    if metadata_dict.get("title"):
        string += f'{metadata_dict["title"]}. '
    if metadata_dict.get("publisher"):
        string += f'{metadata_dict["publisher"]}, '
    if metadata_dict.get("object_id"):
        string += f'{metadata_dict["object_id"]}'

    string = string.strip()
    if string.endswith(","):
        string = string[:-1]
    if not string.endswith("."):
        string += "."

    return string


def remove_unused_fields(d):
    """
    Remove from the dictionary fields that should not be in the final output.
    """
    copy = dict(d)
    copy.pop("title", None)
    return copy


def get_file_type(object_id, app_ctx, request_state):
    """
    Get the type of file from the object_id.
    """
    query_txt = '{{ datanode (object_id: "{}") {{ type }} }}'.format(object_id)
    response = send_query(query_txt, app_ctx, request_state)
    records = response.get("datanode", [])
    if not records:
        msg = 'object_id "' + object_id + '" not found'
        logger.error(msg)
        raise NotFoundError(msg)
    if "type" not in records[0]:
        msg = f"Unable to get 'type' from record: {records[0]}"
        logger.error(msg)
        raise InternalError(msg)
    file_type = records[0]["type"]
    return file_type


def request_metadata(object_id, app_ctx, request_state):
    """
    Write a query and transmit it to send_query().
    """
    file_type = get_file_type(object_id, app_ctx, request_state)
    response = send_query(
        build_query(object_id, file_type, True), app_ctx, request_state
    )

    # if the file has no core metadata, get the other metadata only
    # TODO inspect the node and add the fields that are there, instead of
    # skipping all CORE_METADATA_QUERY_FIELDS when any of them is missing
    if not has_core_metadata(response, file_type):
        response = send_query(build_query(object_id, file_type), app_ctx, request_state)

    return response


def has_core_metadata(response, file_type):
    """
    Return True if a query response contains core metadata, False otherwise.
    """
    try:
        # try to access the core_metadata
        response[file_type][0]["core_metadata_collections"][0]
    except Exception:
        return False
    return True


def build_query(object_id, file_type, get_core_metadata=False):
    """
    Build the query to get the core metadata.

    Args:
        object_id: the file's GUID.
        file_type: the type of file to query.
        get_core_metadata: True if core metadata can be queried for this file, False otherwise.
    """
    query_txt = '{{ {} (object_id: "{}") {{ '.format(file_type, object_id)
    if get_core_metadata:
        fields = " ".join(CORE_METADATA_QUERY_FIELDS)
        query_txt += "core_metadata_collections {{ {} }} ".format(fields)
    fields = " ".join(METADATA_QUERY_FIELDS)
    query_txt += "{} }} }}".format(fields)
    return query_txt


def send_query(query_txt, app_ctx, request_state):
    """
    Make a graphql query and return the response.
    """
    logger.info(f"Query: {query_txt}")
    data, errors = do_graphql_query(query_txt, {}, app_ctx, request_state)
    if errors:
        logger.error(f"Errors querying; will still try to parse data: {errors}")
    return data
