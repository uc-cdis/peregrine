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


def dicts2tsv(dict_list):
    """
    Convert the list of dictionary to tsv format.
    Each element of the list represent a row in tsv
    Args:
        dict_list: list of dictionary
    Return:
        output string
    """
    tsv = ""

    header_set = set()

    for dict_row in dict_list:
        header_set.update(dict_row.keys())

    for h in header_set:
        words = h.split('-')
        tsv = tsv + "{}\t".format(words[-1])
    tsv = tsv[:-1] + "\n"

    nrow = 0
    for dict_row in dict_list:
        for h in header_set:
            if dict_row.get(h):
                tsv = tsv + "{}\t".format(dict_row[h])
            else:
                tsv = tsv + "None\t"
        tsv = tsv[:-1] + "\n"
        nrow = nrow + 1
        if nrow >= 1000:
            break
    return tsv


def join(table_list, L, index, row):
    '''
    Join sub tables to generate a big table

    Args:
        table_list: list of tables. Each table is represented by a list of dictionary
        L: joined table that is iteratively updated
        index: int
        row: dictionary

    Return: None
    '''
    if index == len(table_list):
        L.append(row)
    else:
        for item in table_list[index]:
            newrow = row.copy()
            newrow.update(item)
            join(table_list, L, index + 1, newrow)


def json2tbl(json, prefix, delem):
    '''
    Args:
        json: graphQL output JSON
        prefix: prefix string
        delem: delimitter
    Output: list of dictionary representing a table. Each item in the list represent a row data.
            each row is a dictionary with column name key and value at that position

    '''
    L = []
    if isinstance(json, list) and json != []:
        for l in json:
            L += (json2tbl(l, prefix, delem))
        return L
    if isinstance(json, dict):
        # handle dictionary
        table_list = []
        for k in json.keys():
            table = json2tbl(json[k], prefix + delem + k, delem)
            table_list.append(table)

        join(table_list, L, 0, {})
    else:
        L.append({prefix: json})
    return L
