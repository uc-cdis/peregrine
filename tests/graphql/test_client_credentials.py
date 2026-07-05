"""
Tests for ``client_credentials`` authorization support.

A Fence ``client_credentials`` access token has no user identity (no
``context.user.name``); the OAuth2 client id is carried in the ``azp`` claim.
Peregrine must resolve such a caller's read access against Arborist using
``client_auth_mapping(client_id)`` instead of ``auth_mapping(username)``, while
leaving the user-token flow unchanged.
"""

import json

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from tests.graphql.test_graphql import post_example_entities_together

path = "/v0/submission/graphql"


def test_client_credentials_read_access(
    client, client_token, submitter, pg_driver_clean, cgci_blgsp, mock_arborist_requests
):
    """
    A client_credentials caller with Arborist peregrine/read access to
    CGCI-BLGSP can query and see BLGSP data.
    """
    post_example_entities_together(client, pg_driver_clean, submitter)
    mock_arborist_requests(
        auth_mapping={
            "/programs/CGCI/projects/BLGSP": [
                {"service": "peregrine", "method": "read"}
            ]
        }
    )
    r = client.post(
        path,
        headers=client_token,
        data=json.dumps({"query": "{ project { code } }"}),
    )
    assert r.json == {"data": {"project": [{"code": "BLGSP"}]}}, r.data


def test_client_credentials_uses_client_auth_mapping(
    client, client_token, submitter, pg_driver_clean, cgci_blgsp, mock_arborist_requests
):
    """
    For a client_credentials token, peregrine resolves access via
    client_auth_mapping (keyed by the azp client id) and not auth_mapping.
    """
    post_example_entities_together(client, pg_driver_clean, submitter)
    mock_arborist_requests(
        auth_mapping={
            "/programs/CGCI/projects/BLGSP": [
                {"service": "peregrine", "method": "read"}
            ]
        }
    )
    with patch(
        "gen3authz.client.arborist.client.ArboristClient.client_auth_mapping"
    ) as mocked_client_mapping, patch(
        "gen3authz.client.arborist.client.ArboristClient.auth_mapping"
    ) as mocked_user_mapping:
        mocked_client_mapping.return_value = {
            "/programs/CGCI/projects/BLGSP": [
                {"service": "peregrine", "method": "read"}
            ]
        }
        client.post(
            path,
            headers=client_token,
            data=json.dumps({"query": "{ project { code } }"}),
        )
        mocked_client_mapping.assert_called_once_with("test-client-id")
        mocked_user_mapping.assert_not_called()


def test_user_token_still_uses_auth_mapping(
    client, submitter, pg_driver_clean, cgci_blgsp, mock_arborist_requests
):
    """
    Backward compatibility: a user token continues to be resolved via
    auth_mapping(username), not client_auth_mapping.
    """
    post_example_entities_together(client, pg_driver_clean, submitter)
    with patch(
        "gen3authz.client.arborist.client.ArboristClient.client_auth_mapping"
    ) as mocked_client_mapping, patch(
        "gen3authz.client.arborist.client.ArboristClient.auth_mapping"
    ) as mocked_user_mapping:
        mocked_user_mapping.return_value = {
            "/programs/CGCI/projects/BLGSP": [
                {"service": "peregrine", "method": "read"}
            ]
        }
        client.post(
            path,
            headers=submitter,
            data=json.dumps({"query": "{ project { code } }"}),
        )
        mocked_user_mapping.assert_called_once_with("submitter")
        mocked_client_mapping.assert_not_called()


def test_client_credentials_unknown_to_arborist(
    client, client_token, submitter, pg_driver_clean, cgci_blgsp, mock_arborist_requests
):
    """
    A client_credentials caller unknown to Arborist gets no Arborist-derived
    projects (the request must not 500).
    """
    post_example_entities_together(client, pg_driver_clean, submitter)
    mock_arborist_requests(known_client=False)
    r = client.post(
        path,
        headers=client_token,
        data=json.dumps({"query": "{ project { code } }"}),
    )
    assert r.json == {"data": {"project": []}}, r.data
