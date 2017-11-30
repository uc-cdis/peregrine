from flask import current_app as app
import json
from urlparse import parse_qs
import socket
from flask import Response
from ...utils.pyutils import get_s3_conn
from ...errors import UserError, InternalError
from util import (
    SUBMITTED_STATE, UPLOADING_STATE,
    SUCCESS_STATE, ERROR_STATE)
ALLOWED_STATES = [ERROR_STATE, SUBMITTED_STATE, UPLOADING_STATE]

PERMISSIONS = {
    'list_parts': 'read', 'abort_multipart': 'create',
    'get_file': 'download', 'complete_multipart': 'create',
    'initiate_multipart': 'create', 'upload': 'create',
    'upload_part': 'create', 'delete': 'delete'}


def proxy_request(project_id, uuid, data, args, headers, method, action, dry_run=False):
    node = get_node(project_id, uuid)
    if (action in ["upload", "initiate_multipart"]
        and node.file_state not in ALLOWED_STATES) or\
       (action in ["upload_part", "complete_multipart",
                   "list_parts", "abort_multipart"]
        and node.file_state != UPLOADING_STATE) or\
       (action == "get_file" and node.file_state != SUCCESS_STATE):

        raise UserError("File in {} state, {} not allowed"
                        .format(node.file_state, action))

    signpost_obj = get_signpost(uuid)
    if dry_run:
        message = ("Transaction would have been successful. "
                   "User selected dry run option, "
                   "transaction aborted, no data written to object storage.")
        return Response(json.dumps({'message': message}), status=200)

    if action in ["upload", "initiate_multipart"]:
        update_state(node, UPLOADING_STATE)
    elif action == "abort_multipart":
        update_state(node, SUBMITTED_STATE)
    if action not in ['upload', 'upload_part', 'complete_multipart']:
        data = ""

    resp = make_s3_request(
        project_id, uuid, data, args, headers, method, action)
    if action in ["upload", "complete_multipart"]:
        if resp.status == 200:
            update_signpost_url(signpost_obj, project_id+'/'+uuid)
            update_state(node, SUCCESS_STATE)
    if action == 'delete':
        if resp.status == 204:
            update_state(node, SUBMITTED_STATE)
            update_signpost_url(signpost_obj, None)
    return resp


def make_s3_request(project_id, uuid, data, args, headers, method, action):
    key_name = project_id + '/' + uuid
    bucket = None
    if action in ['upload_part', 'list_parts',
                  'complete_multipart', 'abort_multipart']:
        upload_id = parse_qs(args)['uploadId'][0]
        for ip in get_s3_hosts():
            bucket = get_submission_bucket()
            res = bucket.connection.make_request(
                'GET', bucket=bucket.name, key=key_name,
                data="", query_args="uploadId={}".format(upload_id),
                headers=headers)

            if res.status != 404:
                break
        if res.status == 404 or action == 'list_parts':
            return res

    bucket = bucket or get_submission_bucket()
    res = bucket.connection.make_request(
        method, bucket=bucket.name, key=key_name,
        data=data, query_args=args, headers=headers)
    return res


def get_s3_hosts():
    return set(ip for (a, b, c, d, (ip, port)) in
               socket.getaddrinfo(app.config['SUBMISSION']['host'], 80))


def get_node(project_id, uuid, db=None):
    if db is None:
        db = app.db
    with db.session_scope():
        node = db.nodes().ids(uuid).props(project_id=project_id).first()
    if node:
        return node
    else:
        raise UserError("File {} doesn't exist in {}"
                        .format(uuid, project_id))


def update_state(node, state):
    with app.db.session_scope() as s:
        s.add(node)
        node.file_state = state


def get_signpost(uuid):
    signpost_obj = app.signpost.get(uuid)
    if signpost_obj is None:
        raise InternalError(
            "Signpost entry for {} doesn't exist".format(uuid))
    return signpost_obj


def update_signpost_url(signpost_obj, key_name):
    if key_name:
        url = "s3://{host}/{bucket}/{name}".format(
            host=app.config['SUBMISSION']['host'],
            bucket=app.config['SUBMISSION']['bucket'],
            name=key_name)
        signpost_obj.urls = [url]
    else:
        signpost_obj.urls = []
    signpost_obj.patch()


def get_submission_bucket():
    conn = get_s3_conn(app.config['SUBMISSION']['host'])
    return conn.get_bucket(app.config['SUBMISSION']['bucket'])
