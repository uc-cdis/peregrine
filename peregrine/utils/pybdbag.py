import os
import re
import bagit
import csv
import zipfile
import tempfile
import shutil
import uuid

from flask import current_app


from peregrine.resources.submission.graphql.node import get_fields


def get_node_set(nodetype):
    ns_field = get_fields()
    data_files = set()
    for (k, v) in ns_field.iteritems():
        if k._dictionary['category'] == nodetype:
            data_files.update([str(v)])
    return data_files


def is_category(node_name, data_files):
    for item in data_files:
        if node_name.find(item) >= 0:
            return True
    return False


def is_uuid(uuid):
    if uuid.startswith('dg.'):
        return True
    pattern = re.compile(
        "^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$")
    if pattern.match(uuid):
        return True
    return False

def trim_uri(uri):
    return uri.replace("s3://", "").replace("gs://", "").replace("http://", "").replace("https://", "")

def create_bdbag(bag_info, payload, max_row=1000):
    """Modify from https://github.com/BD2KGenomics/dcc-dashboard-service/blob/feature/manifest-handover/webservice.py
    Create compressed BDbag file.
    Args:
        bag_info: bdbag info
        payload(json): resutl of graphql given a query
        max_row(int): the row limitation of tsv files
    Returns:
        the path of bdbag zip file
    """

    if len(payload) == 0:
        return
    data_files = get_node_set('data_file')
    tmp_dir = tempfile.mkdtemp()
    bag_path = tmp_dir + '/manifest_bag'
    os.makedirs(bag_path)
    bag = bagit.make_bag(bag_path, bag_info)

    data_file_uuids = set()

    for node_name, json_data in payload.iteritems():
        header_set = set()
        data_file_headers = set()
        for dict_row in json_data:
            for key in dict_row.keys():
                if (dict_row[key] is not None and dict_row[key] != []):
                    header_set.update([key])
                    words = key.split('-')
                    if len(words) > 1 and is_category(words[-2], data_files):
                        data_file_headers.update([key])

        for dict_row in json_data:
            for h in data_file_headers:
                if dict_row.get(h) and is_uuid(dict_row[h]):
                    data_file_uuids.update([dict_row[h]])

        header_set = sorted(header_set)

        with open(bag_path + '/data/' + node_name + '.tsv', 'w') as tsvfile:
            writer = csv.writer(tsvfile, delimiter='\t')
            row = []
            for h in header_set:
                words = h.split('-')
                header = words[-1]
                row = row + [header]
                if header[0] == '_':
                    unique_id_header = 'entity:' + header[1:]
            row.insert(0, unique_id_header)
            writer.writerow(row)

            nrow = 0
            for dict_row in json_data:
                row = [str(uuid.uuid4())] # unique id
                for h in header_set:
                    if dict_row.get(h):
                        value = dict_row[h]
                        if 'file_dos' in h:
                            value = 'dos://' + value
                        row = row + [value]
                    else:
                        row = row + ["None"]
                nrow = nrow + 1
                writer.writerow(row)
                if nrow >= max_row:
                    break

    with open(bag_path + '/fetch.txt', 'w') as fetch_file:
        for item in data_file_uuids:
            document = current_app.index_client.get(item)
            if document:
                fetch_file.write(
                    'dos://' + item + '\t' + str(document.size) + '\tdata/' + str(trim_uri(document.urls[0])) + '\n')
            else:
                fetch_file.write(item + '\n')

    bag.save(manifests=True)  # creates checksum manifests
    # Compress bag.
    zip_dir = bag_path
    zip_file_name = tmp_dir + '/manifest_bag.zip'
    zipf = zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED)
    zipdir(zip_dir, zipf)
    zipf.close()
    shutil.rmtree(zip_dir)
    return zip_file_name


def zipdir(path, ziph):
    length = len(path)
    # ziph is zipfile handle
    for root, _, files in os.walk(path):
        folder = root[length:]  # path without "parent"
        for file in files:
            ziph.write(os.path.join(root, file), os.path.join(folder, file))
