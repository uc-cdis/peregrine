from flask import jsonify, request, Blueprint, make_response
from flask import current_app as app
import json

from ...esutils.response import merge_summary
from ... import utils
from ...utils.request import parse_request
from ...utils.response import add_content_disposition, format_response
from ...services import quick, ui, logging, report
from ...models.mapping import mapping
from gdcdatamodel.models.notifications import Notification


blueprint = Blueprint('misc', 'misc_v0')


@blueprint.route('/all', methods=['GET'])
def get_all():
    request_options, mimetype, _ = parse_request(request)
    response = format_response(request_options, quick.search(request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "quick.search")


@blueprint.route('/gql/_mapping', methods=['GET'])
def get_gql_mapping():
    return jsonify(mapping['gql'])


@blueprint.route('/ui/search/summary', methods=['GET', 'POST'])
def get_ui_summary():
    options, _, _ = parse_request(request)
    if isinstance(options, basestring):
        options = json.loads(options)

    case_data = ui.get_case_summary(options)
    file_data = ui.get_file_summary(options)

    fields = ["access", "data_type", "data_format", "experimental_strategy",
              "project.primary_site", "project.project_id"]

    data = merge_summary(case_data, file_data, fields)

    return jsonify(data)


@blueprint.route('/status', methods=['GET'])
def get_status():
    return jsonify(utils.get_status())


@blueprint.route('/reports/data-download-statistics', methods=['GET'])
def get_reports():
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, report.search(request_options, index=app.config["GDC_ES_STATS_INDEX"]), mimetype)
    return add_content_disposition(request.headers, request_options, response, "reports")


@blueprint.route('/errors', methods=['POST'])
def logs():
    logging.log_error(request)
    return "", 200


@blueprint.route('/_echo/<filename>', methods=['POST', 'PUT'])
def download_echo(filename):
    response = make_response(request.get_data())
    response.headers["Content-Disposition"] = (
        "attachment; filename={}".format(filename))
    return response


def filter_notifications_by_components(query):
    """Filters notifications by comma separated ``?component=``"""

    components_param = request.args.get('component', None)
    if components_param is not None:
        components = components_param.split(',')
        query = query.filter(Notification.components.contains(components))

    return query


@blueprint.route('/notifications', methods=['GET'])
def get_notifications():
    """Returns a JSON representation of a list of all Notification objexts"""

    try:
        with app.db.session_scope():
            query = app.db.nodes(Notification)
            query = filter_notifications_by_components(query)
            notifications = query.all()

        return jsonify({
            'data': [note.to_json() for note in notifications]
        }), 200

    except Exception as e:
        app.logger.exception(e)

        return jsonify({
            'errors': [{"message": "Unable to retrieve notifications."}]
        }), 500
