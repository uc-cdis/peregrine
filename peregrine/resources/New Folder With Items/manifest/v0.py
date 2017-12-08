import datetime

from flask import jsonify, request, Blueprint, Response

from ...utils.request import parse_request
from ...utils.response import remove_download_token_from_cookie
from ...download.utils import get_manifest
from ...download import get_nodes, Stream
from compiler.ast import flatten

blueprint = Blueprint('manifest', 'manifest_v0')


@blueprint.route('/<dids>', methods=['GET'])
@blueprint.route('', methods=['POST'])
def manifest(dids=""):
    options, _, _ = parse_request(request)

    if request.method == 'POST':
        # the `ids` in options can be just a string (because of the way #parse_request parses form fields) therefore we use #flatten here to ensure `dids_list` is a list.
        dids_list = flatten([options.get('ids', [])])
    else:
        dids_list = dids.split(",")

    if len(dids_list) == 0:
        return jsonify({"warning": "no ids sent"})

    nodes = get_nodes(dids_list)
    streams = [Stream.from_node(node, lazy=True) for node in nodes]
    manifest = get_manifest(streams)

    response = Response(manifest, mimetype="text/plain")

    current_time = datetime.datetime.now()

    manifest_name = 'gdc_manifest_{date}_{time}.txt'.format(
        date=current_time.strftime('%Y%m%d'),
        time=current_time.strftime('%H%M%S'),
    )

    response.headers.add('Content-Disposition', 'attachment',
        filename=manifest_name,
    )

    return remove_download_token_from_cookie(options, response)
