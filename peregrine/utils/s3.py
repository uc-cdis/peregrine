import boto3
import flask

UPLOAD_SUCCESS = True
UPLOAD_FAIL = False

def put_data_to_s3(filename, key_name):
    bucket_name = flask.current_app.config['SUBMISSION']['bucket']

    data = open(filename, 'rb')
    config = flask.current_app.config["STORAGE"]["s3"]

    try:
        s3 = boto3.resource(
            's3',
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"])
        s3.Bucket(bucket_name).put_object(Key=key_name, Body=data)
        return UPLOAD_SUCCESS
    except Exception:
        return UPLOAD_FAIL


def generate_presigned_url(keyname):
    config = flask.current_app.config["STORAGE"]["s3"]
    bucket_name = flask.current_app.config['SUBMISSION']['bucket']

    client = boto3.client(
        's3',
        aws_access_key_id=config["access_key"],
        aws_secret_access_key=config["secret_key"])

    url = client.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': bucket_name,
            'Key': keyname,
            'ResponseContentDisposition': 'attachment; filename=manifest_bag.zip',
            'ResponseContentType': 'application/zip'
        }
    )
    return url
