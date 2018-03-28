import os
import copy
import bagit
import csv
import zipfile
import tempfile

from flask import Response


def create_bdbag(bag_info, payload, max_row=10000):
    """Modify from https://github.com/BD2KGenomics/dcc-dashboard-service/blob/feature/manifest-handover/webservice.py
    Create compressed BDbag file."""

    if len(payload) == 0:
        return

    # if not os.path.exists(bag_path):
    #     os.makedirs(bag_path)
    tmp_dir = tempfile.mkdtemp()
    bag_path = tmp_dir + '/manifest_bag'
    os.makedirs(bag_path)
    bag = bagit.make_bag(bag_path, bag_info)
    # Add payload in subfolder "data".

    # """Create compressed BDbag file."""
    # if not os.path.exists(bag_path):
    #     os.makedirs(bag_path)
    # bag = bagit.make_bag(bag_path, bag_info)

    header_set = set()

    for dict_row in payload:
        header_set.update(dict_row.keys())

    with open(bag_path + '/data/manifest.tsv', 'w') as tsvfile:
        writer = csv.writer(tsvfile, delimiter='\t')
        row = []
        for h in header_set:
            words = h.split('-')
            row = row + [words[-1]]
        writer.writerow(row)

        nrow = 0
        for dict_row in payload:
            row = []
            for h in header_set:
                if dict_row.get(h):
                    row = row + [dict_row[h]]
                else:
                    row = row + ["None"]
            nrow = nrow + 1
            writer.writerow(row)
            if nrow >= 1000:
                break

    bag.save(manifests=True)  # creates checksum manifests
    # Compress bag.
    #zip_dir = os.path.basename(os.path.normpath(str(bag)))
    zip_dir = bag_path
    zip_file_name = tmp_dir + '/manifest_bag.zip'
    zipf = zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED)
    zipdir(zip_dir, zipf)
    zipf.close()
    return zip_file_name


def zipdir(path, ziph):
    length = len(path)
    # ziph is zipfile handle
    for root, _, files in os.walk(path):
        folder = root[length:]  # path without "parent"
        for file in files:
            ziph.write(os.path.join(root, file), os.path.join(folder, file))
