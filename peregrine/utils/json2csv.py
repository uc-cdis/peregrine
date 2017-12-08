import csv
from cStringIO import StringIO
from functools import reduce, partial


def list_to_obj(k, v):
    return {'{}_{}'.format(k, i): x for i, x in enumerate(v)}


def flatten_nested_obj(k, v):
    return {'{}_{}'.format(k, k2): v2 for (k2, v2) in v.iteritems()}


def pair_to_obj(acc, (k, v), parent=None):
    p = '{}_{}'.format(parent, k) if parent else k
    if isinstance(v, list):
        acc.update(flatten_obj(list_to_obj(p, v)))
    elif isinstance(v, dict):
        acc.update(flatten_obj(v, parent=p))
    else:
        acc[p] = v

    return acc


def flatten_obj(json, parent=None):
    p_pair_to_json = partial(pair_to_obj, parent=parent)
    return reduce(p_pair_to_json, json.iteritems(), {})


def row_with_headers((rows, header), hit):
    f_o = flatten_obj(hit)
    rows.append(f_o)

    return rows, header.union(f_o.keys())


def rows_with_headers(hits):
    return reduce(row_with_headers, hits, ([], set()))


def to_csv(hits, dialect='excel'):
    s = StringIO()
    rows, headers = rows_with_headers(hits)
    writer = csv.DictWriter(s, fieldnames=headers, dialect=dialect)
    writer.writeheader()
    writer.writerows(rows)

    return s.getvalue()
