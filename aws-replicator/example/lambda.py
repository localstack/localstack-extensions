import boto3


def handler(event, context):
    s3 = boto3.client("s3")
    buckets = s3.list_buckets().get("Buckets")
    print(buckets)
