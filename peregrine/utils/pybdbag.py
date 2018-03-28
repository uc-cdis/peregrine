import os
import copy
import bagit
import csv
import zipfile
import tempfile
import shutil

from flask import Response


def create_bdbag(bag_info, payload, max_row=1000):
    """Modify from https://github.com/BD2KGenomics/dcc-dashboard-service/blob/feature/manifest-handover/webservice.py
    Create compressed BDbag file.
    Args:
        bag_info: bdbag info
        payload(json): resutl of graphql given a query
        max_row(int): the row limitation of tsv files
    Return:
        the path of bdbag zip file
    """

    if len(payload) == 0:
        return

    tmp_dir = tempfile.mkdtemp()
    bag_path = tmp_dir + '/manifest_bag'
    os.makedirs(bag_path)
    bag = bagit.make_bag(bag_path, bag_info)

    for node_name, json_data in payload.iteritems():
        header_set = set()

        for dict_row in json_data:
            header_set.update(dict_row.keys())

        with open(bag_path + '/data/' + node_name+ '.tsv', 'w') as tsvfile:
            writer = csv.writer(tsvfile, delimiter='\t')
            row = []
            for h in header_set:
                words = h.split('-')
                row = row + [words[-1]]
            writer.writerow(row)

            nrow = 0
            for dict_row in json_data:
                row = []
                for h in header_set:
                    if dict_row.get(h):
                        row = row + [dict_row[h]]
                    else:
                        row = row + ["None"]
                nrow = nrow + 1
                writer.writerow(row)
                if nrow >= max_row:
                    break

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
