import os
import copy
import bagit
import csv
import zipfile


def create_bdbag(bag_path, bag_info, payload, max_row=10000):
    """Modify from https://github.com/BD2KGenomics/dcc-dashboard-service/blob/feature/manifest-handover/webservice.py
    Create compressed BDbag file."""

    if len(payload) == 0:
        return
    if not os.path.exists(bag_path):
        os.makedirs(bag_path)
    bag = bagit.make_bag(bag_path, bag_info)
    # Add payload in subfolder "data".

    with open(bag_path + '/data/manifest.tsv', 'w') as tsvfile:
        writer = csv.writer(tsvfile, delimiter='\t')
        #write header
        row = []
        for k in payload[0].keys():
            k = k.replace('_data_','')
            row.append(k)
        header = copy.deepcopy(row)
        writer.writerow(row)
        nrow = 1
        print('==============header==========')
        print(header)
        for row_dict in payload:
            row=[]
            print(row_dict)
            for h in header:
                if row_dict.get('_data_'+h):
                    row.append(row_dict.get('_data_'+h))
                else:
                    row.append('None')
            writer.writerow(row)
            nrow = nrow + 1
            if nrow >= max_row:
                break
        
    bag.save(manifests=True)  # creates checksum manifests
    # Compress bag.
    zip_file_path = os.path.basename(os.path.normpath(str(bag)))
    zip_file_name = 'manifest_bag.zip'
    zipf = zipfile.ZipFile(zip_file_name, 'w', zipfile.ZIP_DEFLATED)
    zipdir(zip_file_path, zipf)
    zipf.close()
    #new_zip_path = '/app/' + zip_file_name
    return zip_file_name


def zipdir(path, ziph):
    """https://github.com/BD2KGenomics/dcc-dashboard-service/blob/feature/manifest-handover/webservice.py"""
    # ziph is zipfile handle
    for root, _, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file))
