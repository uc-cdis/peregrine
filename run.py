#!/usr/bin/env python

from authutils import ROLES as all_roles
from collections import defaultdict
from mock import patch, PropertyMock
import os
from peregrine.api import run_for_development
from psqlgraph import PolyNode as Node
import requests

requests.packages.urllib3.disable_warnings()

all_role_values = list(all_roles.values())
roles = defaultdict(lambda: all_role_values)


class FakeBotoKey(object):
    def __init__(self, name):
        self.name = name

    def close(self):
        pass

    def open_read(self, *args, **kwargs):
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
        nodes.append(
            Node(
                node_id=did,
                label="file",
                acl=["open"],
                properties={
                    "file_name": file_name,
                    "file_size": len("fake data for {}".format(did)),
                    "md5sum": "fake_md5sum",
                    "state": "live",
                },
            )
        )
    return nodes


def fake_urls_from_index_client(did):
    return ["s3://fake-host/fake_bucket/{}".format(did)]


def fake_key_for(parsed):
    return FakeBotoKey(parsed.netloc.split("/")[-1])


def fake_key_for_node(node):
    return FakeBotoKey(node.node_id)


class FakeUser(object):
    username = "test"
    roles = roles


def set_user(*args, **kwargs):
    from flask import g

    g.user = FakeUser()


def run_with_fake_auth():
    with patch(
        "peregrine.auth.CurrentUser.roles",
        new_callable=PropertyMock,
        return_value=roles,
    ), patch(
        "peregrine.auth.CurrentUser.logged_in",
        new_callable=PropertyMock,
        return_value=lambda: True,
    ), patch(
        "peregrine.auth.verify_hmac", new=set_user
    ):
        run_for_development(debug=debug, threaded=True)


def run_with_fake_authz():
    """
    By mocking `get_read_access_projects`, we avoid checking the
    Authorization header and access token, and avoid making arborist
    calls to fetch a list of authorized resources.
    """
    # `user_projects` contains a list of `project_id`s (in format
    # "<program.name>-<project.code>") the user has access to.
    # Update it to mock specific access:
    user_projects = []
    with patch(
        "peregrine.resources.submission.get_read_access_resources",
        return_value=user_projects,
    ):
        run_for_development(debug=debug, threaded=True)


def run_with_fake_download():
    with patch("peregrine.download.get_nodes", fake_get_nodes):
        with patch.multiple(
            "peregrine.download",
            key_for=fake_key_for,
            key_for_node=fake_key_for_node,
            urls_from_index_client=fake_urls_from_index_client,
        ):
            if os.environ.get("GDC_FAKE_AUTH"):
                run_with_fake_auth()
            else:
                run_for_development(debug=debug, threaded=True)


if __name__ == "__main__":
    debug = bool(os.environ.get("PEREGRINE_DEBUG", True))
    if os.environ.get("GDC_FAKE_DOWNLOAD") == "True":
        run_with_fake_download()
    else:
        if os.environ.get("GDC_FAKE_AUTH") == "True":
            run_with_fake_auth()
        else:
            run_with_fake_authz()
