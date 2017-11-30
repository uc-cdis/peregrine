from flask import Blueprint, request

from ...services import analysis
from ...utils.request import parse_request
from ...utils.response import add_content_disposition, format_response

blueprint = Blueprint('analysis', 'analysis_v0')


@blueprint.route('/survival', methods=['GET', 'POST'])
def get_projects():
    request_options, mimetype, is_csv = parse_request(request)
    response = format_response(request_options, analysis.survival.survival(request_options), mimetype)
    return add_content_disposition(request.headers, request_options, response, "survival")
