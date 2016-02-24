from emailcongress.settings.shared import *

# see http://developer.yahoo.com/performance/rules.html#expires
AWS_HEADERS = {
    'Expires': 'Thu, 31 Dec 2099 20:00:00 GMT',
    'Cache-Control': 'max-age=94608000',
}

AWS_STORAGE_BUCKET_NAME = CONFIG_DICT['aws']['storage_bucket_name']
AWS_ACCESS_KEY_ID = CONFIG_DICT['aws']['access_key_id']
AWS_SECRET_ACCESS_KEY = CONFIG_DICT['aws']['secret_access_key']

AWS_S3_CUSTOM_DOMAIN = '%s.s3.amazonaws.com' % AWS_STORAGE_BUCKET_NAME

STATIC_URL = "https://%s/" % AWS_S3_CUSTOM_DOMAIN

STATICFILES_STORAGE = 'storages.backends.s3boto.S3BotoStorage'