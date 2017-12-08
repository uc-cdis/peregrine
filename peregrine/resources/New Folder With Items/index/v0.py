from flask import Blueprint, request, jsonify, Response

from flask import stream_with_context
import copy

from ...models.mapping import mapping
from ...services import (
    cases, files, projects, annotations, logging)
from ...utils.request import parse_request
from ...utils.response import add_content_disposition, format_response, to_json

blueprint = Blueprint('index', 'index_v0')


# private helpers
def _stream_json(generator, options):
    """
        Processes (reads, serializes & transforms) the scroll_search result for each iteration of the generator.

        Args:
            generator (generator): generator from scroll_search
            options (dict): request options

        Returns:
            yields the processed result
    """
    for hits, batch_id, number_of_batches in generator:
        data = [hit.get('_source', {}) for hit in hits]
        yield _customize_streaming_json(to_json(options, data), batch_id, number_of_batches)


def _customize_streaming_json(json, batch_id, number_of_batches):
    """
        Makes sure the final combined file is a valid json.

        Args:
            json (string): a serialized json array.
            batch_id (int): current batch ID from scroll search
            number_of_batches (int): number of batches expected

        Returns:
            result (string): processed result
    """
    # Strips off the opening and closing square brackets
    result = json[1 : -1]

    # batch_id is one-based.
    if batch_id == 1:
        result = '[' + result

    if batch_id == number_of_batches:
        result = result + ']'

    if batch_id < number_of_batches:
        result = result + ','

    return result


def _stream_text(generator, options):
    """
        Processes (reads, serializes & transforms) the scroll_search result for each iteration of the generator.

        Args:
            generator (generator): generator from scroll_search
            options (dict): request options

        Returns:
            yields the processed result
    """
    for hits, batch_id, _ in generator:
        data = [hit.get('fields', {}) for hit in hits]

        # TODO:
        # 1) transform data into a flat table
        # 2) build the header row
        content = data
        header = ''

        yield _customize_streaming_text(content, header, batch_id)


def _customize_streaming_text(text, header, batch_id):
    """
        Add header row to the first line.

        Args:
            text (string): rows of text
            batch_id (int): current batch ID from scroll search

        Returns:
            result (string): processed result
    """
    return ('{}\n{}'.format(header, text) if batch_id == 1 # batch_id is one-based
        else text)


STREAM_PROCESSORS = {
    'application/json': _stream_json
    # 'text/tab-separated-values': _stream_text,
    # 'text/csv': _stream_text
}


@blueprint.route('/projects', methods=['GET', 'POST'])
def get_projects():
    logging.log_entity("projects", request)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, projects.search(request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "projects")


@blueprint.route('/projects/_mapping', methods=['GET'])
def get_projects_mapping():
    return jsonify(mapping['project'])


@blueprint.route('/projects/<project_id>', methods=['GET', 'POST'])
def get_project(project_id):
    logging.log_entity("projects", request, pid=project_id)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, projects.get(project_id, request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "project.{}".format(project_id))


@blueprint.route('/projects/ids', methods=['GET'])
def suggest_projects():
    logging.log_entity("projects/ids", request)
    request_options, mimetype, _ = parse_request(request)
    response = format_response(request_options, projects.multi_match(request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "projects.ids")


@blueprint.route('/cases', methods=['GET', 'POST'])
def get_cases():
    logging.log_entity("cases", request)
    request_options, mimetype, is_csv = parse_request(request)

    if request_options.get('attachment', '').lower() == 'true' and STREAM_PROCESSORS.get(mimetype, False):
        data_processor = STREAM_PROCESSORS.get(mimetype)
        generator = data_processor(cases.scroll_search(request_options), copy.deepcopy(request_options))

        response = Response(stream_with_context(generator), mimetype = mimetype)
    else:
        response = format_response(request_options, cases.search(request_options), mimetype)

    return add_content_disposition(request.headers, request_options, response, "cases")


@blueprint.route('/cases/_mapping', methods=['GET'])
def get_cases_mapping():
    return jsonify(mapping['case'])


@blueprint.route('/cases/<case_id>', methods=['GET', 'POST'])
def get_case(case_id):
    logging.log_entity("cases", request, pid=case_id)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, cases.get(case_id, request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "case.{}".format(case_id))


@blueprint.route('/cases/ids', methods=['GET'])
def suggest_cases():
    logging.log_entity("cases/ids", request)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, cases.multi_match(request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "cases.ids")


@blueprint.route('/files', methods=['GET', 'POST'])
def get_files():
    logging.log_entity("files", request)
    request_options, mimetype, is_csv = parse_request(request)

    if request_options.get('return_type') == 'manifest':
        content, file_name = files.manifest(request_options)
        response = Response(content, mimetype="text/plain")
        request_options.update({'attachment': True, 'format': 'tsv'})
        return add_content_disposition(
            {'Content-Type': 'tab-separated-values'},
            request_options,
            response,
            file_name=file_name)

    if request_options.get('attachment', '').lower() == 'true' and STREAM_PROCESSORS.get(mimetype, False):
        data_processor = STREAM_PROCESSORS.get(mimetype)
        generator = data_processor(files.scroll_search(request_options), copy.deepcopy(request_options))

        response = Response(stream_with_context(generator), mimetype = mimetype)
    else:
        response = format_response(request_options, files.search(request_options), mimetype)

    return add_content_disposition(request.headers, request_options, response, "files")


@blueprint.route('/files/_mapping', methods=['GET'])
def get_files_mapping():
    return jsonify(mapping['file'])


@blueprint.route('/files/<file_id>', methods=['GET', 'POST'])
def get_file(file_id):
    logging.log_entity("files", request, pid=file_id)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, files.get(file_id, request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "files.{}".format(file_id))


@blueprint.route('/files/ids', methods=['GET'])
def suggest_files():
    logging.log_entity("files/ids", request)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, files.multi_match(request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "files.ids")


@blueprint.route('/annotations', methods=['GET', 'POST'])
def get_annotations():
    logging.log_entity("annotations", request)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, annotations.search(request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "annotations")


@blueprint.route('/annotations/_mapping', methods=['GET'])
def get_annotations_mapping():
    return jsonify(mapping['annotation'])


@blueprint.route('/annotations/<annotation_id>', methods=['GET', 'POST'])
def get_annotation(annotation_id):
    logging.log_entity("annotations", request, pid=annotation_id)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, annotations.get(annotation_id, request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "annotation.{}".format(annotation_id))


@blueprint.route('/annotations/ids', methods=['GET'])
def suggest_annotations():
    logging.log_entity("annotations/ids", request)
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, annotations.multi_match(request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "annotations.ids")
