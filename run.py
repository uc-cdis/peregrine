#!/usr/bin/env python

import os
from peregrine.api import run_for_development
from flask import current_app

from mock import patch, PropertyMock

from psqlgraph import PolyNode as Node
from peregrine.auth import ROLES as all_roles
from collections import defaultdict
import requests
requests.packages.urllib3.disable_warnings()


all_role_values = all_roles.values()
roles = defaultdict(lambda: all_role_values)


class FakeBotoKey(object):

    def __init__(self, name):
        self.name = name

    def close(self):
        pass

    def open_read(self,*args, **kwargs):
        pass

    @property
    def size(self):
        return len("fake data for {}".format(self.name))

    def __iter__(self):
        for string in ["fake ", "data ", "for ", self.name]:
            yield string


def fake_get_nodes(dids):
    nodes = []
    for did in dids:
        try:
            file_name = files.get(did, {})["data"]["file_name"]
        except ValueError:
            file_name = did
        nodes.append(Node(
            node_id=did,
            label="file",
            acl=["open"],
            properties={
                "file_name": file_name,
                "file_size": len("fake data for {}".format(did)),
                "md5sum": "fake_md5sum",
                "state": "live",
            },
        ))
    return nodes


def fake_urls_from_index_client(did):
    return ["s3://fake-host/fake_bucket/{}".format(did)]


def fake_key_for(parsed):
    return FakeBotoKey(parsed.netloc.split("/")[-1])


def fake_key_for_node(node):
    return FakeBotoKey(node.node_id)


class FakeUser(object):
    username = 'test'
    roles =  roles


def set_user(*args, **kwargs):
    from flask import g
    g.user = FakeUser()


def run_with_fake_auth():
    from datamodelutils import models as md
    def get_project_ids(role='_member_', project_ids=None):
        if project_ids is None:
            project_ids = []
        if not project_ids:
            with current_app.db.session_scope():
                project_ids += [
                    '{}-{}'.format(p.programs[0].name, p.code)
                    for p in current_app.db.nodes(md.Project).all()]
        return project_ids

    with patch(
        'peregrine.auth.CurrentUser.roles',
        new_callable=PropertyMock,
        return_value=roles,
    ), patch(
        'peregrine.auth.CurrentUser.logged_in',
        new_callable=PropertyMock,
        return_value=lambda: True,
    ), patch(
        'peregrine.auth.CurrentUser.get_project_ids',
        new_callable=PropertyMock,
        return_value=get_project_ids,
    ), patch(
        'peregrine.auth.verify_hmac',
        new=set_user,
    ):
        run_for_development(debug=debug, threaded=True)


def run_with_fake_download():
    with patch("peregrine.download.get_nodes", fake_get_nodes):
        with patch.multiple("peregrine.download",
                            key_for=fake_key_for,
                            key_for_node=fake_key_for_node,
                            urls_from_index_client=fake_urls_from_index_client):
            if os.environ.get("GDC_FAKE_AUTH"):
                run_with_fake_auth()
            else:
                run_for_development(debug=debug, threaded=True)


if __name__ == '__main__':
    debug = bool(os.environ.get('PEREGRINE_DEBUG', True))
    if os.environ.get("GDC_FAKE_DOWNLOAD") == 'True':
        run_with_fake_download()
    else:
        if os.environ.get("GDC_FAKE_AUTH") == 'True':
            run_with_fake_auth()
        else:
            run_for_development(debug=debug, threaded=True)
