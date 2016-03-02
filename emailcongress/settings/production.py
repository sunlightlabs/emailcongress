from emailcongress.settings.shared import *

# see http://developer.yahoo.com/performance/rules.html#expires
AWS_HEADERS = {
    'Expires': 'Thu, 31 Dec 2099 20:00:00 GMT',
    'Cache-Control': 'max-age=94608000',
}

AWS_ACCESS_KEY_ID = CONFIG_DICT['aws']['access_key_id']
AWS_SECRET_ACCESS_KEY = CONFIG_DICT['aws']['secret_access_key']
AWS_STORAGE_BUCKET_NAME = CONFIG_DICT['aws']['storage_bucket_name']

# see https://github.com/boto/boto/issues/2836
AWS_S3_CALLING_FORMAT = 'boto.s3.connection.OrdinaryCallingFormat'
# AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME
AWS_S3_CUSTOM_DOMAIN = 'd1tnme6pnhrkup.cloudfront.net'

# STATIC_URL = "https://%s/" % AWS_S3_CUSTOM_DOMAIN

STATICFILES_STORAGE = 'emailcongress.settings.MyS3BotoStorage'
