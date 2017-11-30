from .. import esutils
from flask import current_app as app
from ..models import file as f
from ..models import case as c

empty_aggs = {
  "access": {
    "buckets": []
  },
  "data_format": {
    "buckets": []
  },
  "data_type": {
    "buckets": []
  },
  "experimental_strategy": {
    "buckets": []
  },
  "fs": {
    "value": 0.0
  },
  "project.primary_site": {
    "buckets": []
  },
  "project.project_id": {
    "buckets": []
  }
}


def get_case_summary(args):

    body = {
        "aggs": {
            "project.primary_site": {
                "terms": {
                    "field": "project.primary_site",
                    "size": 100
                }
            },
            "project.project_id": {
                "terms": {
                    "field": "project.project_id",
                    "size": 100
                }
            },
            "files": {
                "nested": {
                    "path": "files"
                },
                "aggs": {
                    "access": {
                        "terms": {
                            "field": "files.access",
                            "size": 10
                        },
                        "aggs": {
                            "cases": {
                                "reverse_nested": {}
                            }
                        }
                    },
                    "data_type": {
                        "terms": {
                            "field": "files.data_type",
                            "size": 100
                        },
                        "aggs": {
                            "cases": {
                                "reverse_nested": {}
                            }
                        }
                    },
                    "data_format": {
                        "terms": {
                            "field": "files.data_format",
                            "size": 100
                        },
                        "aggs": {
                            "cases": {
                                "reverse_nested": {}
                            }
                        }
                    },
                    "experimental_strategy": {
                        "terms": {
                            "field": "files.experimental_strategy",
                            "size": 100
                        },
                        "aggs": {
                            "cases": {
                                "reverse_nested": {}
                            }
                        }
                    }
                }
            }
        }
    }

    filters = esutils.search.get_filters(args)

    if "filters" in args and filters:
        filters = esutils.request.build_filters(c.doc_type, c.nested_fields, filters)

        body['query'] = {
            "filtered": {
                "query": {
                    "match_all": {}
                },
                "filter": filters
            }
        }

    try:
        res = esutils.search.es_search(
            doc_type=c.doc_type, params={"size": 0},
            body=body, index=app.config["GDC_ES_INDEX"])
    except:
        return empty_aggs

    for field in ["access", "data_format", "data_type", "experimental_strategy"]:
        for item in res["aggregations"]["files"][field]["buckets"]:
            item["case_count"] = item["cases"]["doc_count"];
            item.pop("doc_count", None)

        res["aggregations"][field] = res["aggregations"]["files"][field]

    for field in ["project.primary_site", "project.project_id"]:
        for item in res["aggregations"][field]["buckets"]:
            item["case_count"] = item["doc_count"];
            item.pop("doc_count", None)

    res["aggregations"].pop("files", None)

    return res["aggregations"]


def get_file_summary(args):

    body = {
        "aggs": {
            "fs": {
                "sum": {
                    "field": "file_size"
                }
            },
            "data_type": {
                "terms": {
                    "field": "data_type",
                    "size": 100
                },
                "aggs": {
                    "file_size": {
                        "sum": {
                            "field": "file_size"
                        }
                    }
                }
            },
            "access": {
                "terms": {
                    "field": "access",
                    "size": 100
                },
                "aggs": {
                    "file_size": {
                        "sum": {
                            "field": "file_size"
                        }
                    }
                }
            },
            "data_format": {
                "terms": {
                    "field": "data_format",
                    "size": 100
                },
                "aggs": {
                    "file_size": {
                        "sum": {
                            "field": "file_size"
                        }
                    }
                }
            },
            "experimental_strategy": {
                "terms": {
                    "field": "experimental_strategy",
                    "size": 100
                },
                "aggs": {
                    "file_size": {
                        "sum": {
                            "field": "file_size"
                        }
                    }
                }
            },
            "cases": {
                "nested": {
                    "path": "cases"
                },
                "aggs": {
                    "project.primary_site": {
                        "terms": {
                            "field": "cases.project.primary_site",
                            "size": 100
                        },
                        "aggs": {
                            "files": {
                                "reverse_nested": {},
                                "aggs": {
                                    "file_size": {
                                        "sum": {
                                            "field": "file_size"
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "project.project_id": {
                        "terms": {
                            "field": "cases.project.project_id",
                            "size": 100
                        },
                        "aggs": {
                            "files": {
                                "reverse_nested": {},
                                "aggs": {
                                    "file_size": {
                                        "sum": {
                                            "field": "file_size"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    filters = esutils.search.get_filters(args)

    if "filters" in args and filters:
        filters = esutils.request.build_filters(f.doc_type, f.nested_fields, filters)

        body['query'] = {
            "filtered": {
                "query": {
                    "match_all": {}
                },
                "filter": filters
            }
        }

    try:
        res = esutils.search.es_search(
            doc_type=f.doc_type, params={"size": 0},
            body=body, index=app.config["GDC_ES_INDEX"])
    except:
        return empty_aggs

    for field in ["project.primary_site", "project.project_id"]:
        for item in res["aggregations"]["cases"][field]["buckets"]:
            item["doc_count"] = item["files"]["doc_count"]
            item["file_size"] = item["files"]["file_size"]["value"]
            item.pop("files", None)

        res["aggregations"][field] = res["aggregations"]["cases"][field]

    for field in ["access", "data_format", "data_type", "experimental_strategy"]:
        for item in res["aggregations"][field]["buckets"]:
            item["file_size"] = item["file_size"]["value"]

    res["aggregations"].pop("cases", None)

    return res["aggregations"]
