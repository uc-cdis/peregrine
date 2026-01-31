from fastapi.responses import JSONResponse
import os
import re

from fastapi import APIRouter, Depends, Query, Request
from peregrine.fast_api import get_app_context, get_request_state
from peregrine.resources.submission import (
    graphql,
    set_read_access_projects_for_public_endpoint,
    set_read_access_projects,
)

from cdiserrors import UserError
from dictionaryutils import dictionary

router = APIRouter()


@router.get("/")
def get_datasets(
    nodes: str = Query(""),
    app_ctx=Depends(get_app_context),
    request_state=Depends(get_request_state),
):
    """
    Get dataset level summary counts, if a deployment is configured
    to set PUBLIC_DATASETS to True, this endpoint will be open to
    anonymous users
    """
    if not nodes:
        raise UserError("Need to provide target nodes in query param")
    nodes = nodes.split(",")
    if os.environ.get("PUBLIC_DATASETS", "false").lower() == "true":
        set_read_access_projects_for_public_endpoint(app_ctx, request_state)
    else:
        set_read_access_projects(app_ctx, request_state)
    projects = request_state.read_access_projects
    if not projects:
        return JSONResponse({})
    # construct a query that get counts for all projects
    # because graphql can't add structure to group by projects,
    # we labeled the count by project index and later parse it
    # with regex to add structure to response
    query = "{"
    for i, project_id in enumerate(projects):
        query += (
            " ".join(
                map(
                    lambda x: """i{i}_{node}: _{node}_count(project_id: "{p}")""".format(
                        i=i, node=x, p=project_id
                    ),
                    nodes,
                )
            )
            + " "
        )
    query += "}"
    data, errors = graphql.execute_query(app_ctx, query, variables={})
    if errors:
        return JSONResponse({"data": data, "errors": errors}, status_code=400)
    result = {project_id: {} for project_id in projects}

    for name, value in data.items():
        match = re.search(r"^i(\d+)_(.*)", name)
        index = int(match.group(1))
        node = match.group(2)
        result[projects[index]][node] = value
    return JSONResponse(result)


@router.get("/projects")
def get_projects(
    app_ctx=Depends(get_app_context),
    request_state=Depends(get_request_state),
):
    """
    Get all projects high level information, if a deployment is configured
    to set PUBLIC_DATASETS to True, this endpoint will be open to
    anonymous users
    """
    if os.environ.get("PUBLIC_DATASETS", "false").lower() == "true":
        set_read_access_projects_for_public_endpoint(app_ctx, request_state)
    else:
        set_read_access_projects(app_ctx, request_state)
    projects = request_state.read_access_projects
    if not projects:
        return JSONResponse({"projects": []})
    # construct a query that get counts for all projects
    # because graphql can't add structure to group by projects,
    # we labeled the count by project index and later parse it
    # with regex to add structure to response
    query = "{project (first: 0) { name code dbgap_accession_number "
    for field in ["description", "image_url"]:
        if dictionary.schema["project"]["properties"].get(field):
            query += field + " "

    query += "}}"
    data, errors = graphql.execute_query(app_ctx, query, variables={})
    if errors:
        return JSONResponse({"data": data, "errors": errors}, status_code=400)
    return JSONResponse({"projects": data["project"]})
