import boto3
import flask


def get_s3_client(host):
    """
    Get a connection to a given storage host based on configuration in the
    current app context.
    """
    config = flask.current_app.config["STORAGE"]["s3"]
    return boto3.client(
        's3',
        aws_access_key_id=config["keys"][host]["access_key"],
        aws_secret_access_key=config["keys"][host]["secret_key"]
    )


def get_submission_bucket():
    conn = get_s3_client(flask.current_app.config['SUBMISSION']['host'])
    return conn.get_bucket(flask.current_app.config['SUBMISSION']['bucket'])


def put_data_to_s3(filename, key_name):
    host = flask.current_app.config['SUBMISSION']['host']
    bucket_name = flask.current_app.config['SUBMISSION']['bucket']

    data = open(filename, 'rb')
    config = flask.current_app.config["STORAGE"]["s3"]

    try:
        s3 = boto3.resource(
            's3', 
            aws_access_key_id=config["keys"][host]["access_key"], 
            aws_secret_access_key=config["keys"][host]["secret_key"])
        s3.Bucket(bucket_name).put_object(Key=key_name, Body=data)
        return True
    except Exception:
        return False


def generate_presigned_url(keyname):
    host = flask.current_app.config['SUBMISSION']['host']
    bucket_name = flask.current_app.config['SUBMISSION']['bucket']

    client = get_s3_client(host)
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
