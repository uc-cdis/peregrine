from .test_graphql import post_example_entities_together
from datamodelutils import models


def test_authorized_call_with_protected_config(
    client, submitter, pg_driver_clean, cgci_blgsp
):
    post_example_entities_together(client, pg_driver_clean, submitter)
    #: number of nodes to change project_id on, there should be 5
    with pg_driver_clean.session_scope() as s:
        cases = pg_driver_clean.nodes(models.Case).all()
        case_count = len(cases)
        for case in cases[0:-3]:
            case.project_id = "OTHER-OTHER"
            s.merge(case)
    r = client.get("/datasets?nodes=case,aliquot", headers=submitter)
    assert list(r.json.keys()) == ["CGCI-BLGSP"]
    assert r.json["CGCI-BLGSP"]["case"] == case_count - 2

    r = client.get("/datasets/projects", headers=submitter)
    assert len(r.json["projects"]) == 1


def test_unauthorized_call_with_protected_config(
    client, submitter, pg_driver_clean, cgci_blgsp, mock_arborist_requests
):
    post_example_entities_together(client, pg_driver_clean, submitter)

    mock_arborist_requests(auth_mapping={})

    r = client.get("/datasets?nodes=case,aliquot", headers=submitter)
    assert r.status_code == 200
    assert r.json == {}

    r = client.get("/datasets/projects", headers=submitter)

    assert r.status_code == 200
    assert r.json == {"projects": []}


def test_anonymous_call_with_protected_config(client, pg_driver_clean, cgci_blgsp):
    r = client.get("/datasets?nodes=case,aliquot")
    assert r.status_code == 401


def test_anonymous_projects_call_with_protected_config(
    client, pg_driver_clean, cgci_blgsp
):
    r = client.get("/datasets/projects")
    assert r.status_code == 401


def test_anonymous_call_with_public_config(
    client, submitter, pg_driver_clean, cgci_blgsp, public_dataset_api
):
    post_example_entities_together(client, pg_driver_clean, submitter)
    with pg_driver_clean.session_scope() as s:
        project = models.Project("other", code="OTHER")
        program = pg_driver_clean.nodes(models.Program).props(name="CGCI").first()
        project.programs = [program]
        s.add(project)
        aliquot_count = pg_driver_clean.nodes(models.Aliquot).count()
        cases = pg_driver_clean.nodes(models.Case).all()
        case_count = len(cases)
        for case in cases[0:-3]:
            case.project_id = "CGCI-OTHER"
            s.merge(case)

    r = client.get("/datasets?nodes=case,aliquot")
    assert r.json["CGCI-BLGSP"]["case"] == case_count - 2
    assert r.json["CGCI-BLGSP"]["aliquot"] == aliquot_count
    assert r.json["CGCI-OTHER"]["aliquot"] == 0
    assert r.json["CGCI-OTHER"]["case"] == 2


def test_get_projects_anonymous(
    client, submitter, pg_driver_clean, cgci_blgsp, public_dataset_api
):
    post_example_entities_together(client, pg_driver_clean, submitter)
    with pg_driver_clean.session_scope() as s:
        project = models.Project(
            "other", name="name", code="OTHER", dbgap_accession_number="phsid"
        )
        program = pg_driver_clean.nodes(models.Program).props(name="CGCI").first()
        project.programs = [program]
        s.add(project)
    r = client.get("/datasets/projects")
    assert r.json == {
        "projects": [
            {
                "dbgap_accession_number": "phs000527",
                "code": "BLGSP",
                "name": "Burkitt Lymphoma Genome Sequencing Project",
            },
            {"dbgap_accession_number": "phsid", "code": "OTHER", "name": "name"},
        ]
    }


def test_no_nodes_parameter(client, submitter):
    """
    The endpoint should require the `nodes` query parameter
    """
    r = client.get("/datasets", headers=submitter)
    assert r.status_code == 400, r.text
    assert r.json["message"] == "Need to provide target nodes in query param"


def test_invalid_nodes_parameter(client, submitter):
    """
    Node names that are not real node types must be rejected before being
    interpolated into the GraphQL query, to prevent GraphQL injection via
    the `nodes` query param.
    """
    r = client.get("/datasets?nodes=case,not_a_real_node", headers=submitter)
    assert r.status_code == 400, r.text
    assert "not_a_real_node" in r.json["message"]


def test_graphql_injection_rejected_public_config(
    client, submitter, pg_driver_clean, cgci_blgsp, public_dataset_api
):
    """
    On a PUBLIC_DATASETS deployment the anonymous scope covers all projects.
    A crafted `nodes` value that tries to inject a record-level selection
    must be rejected rather than returning records for controlled projects.
    """
    post_example_entities_together(client, pg_driver_clean, submitter)
    payload = "x:node(first:1){id project_id submitter_id}}#"
    r = client.get("/datasets", query_string={"nodes": payload})
    assert r.status_code == 400, r.text
