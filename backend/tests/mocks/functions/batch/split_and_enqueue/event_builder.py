import os


def build_s3_event(object_key):
    return {
        'Records': [{
            's3': {
                'bucket': {
                    'name': os.environ['RAW_REPORTS_BUCKET_NAME']
                },
                'object': {
                    'key': object_key
                },
            }
        }]
    }
