from django.contrib.staticfiles import storage
import os
from django.conf import settings
from pipeline.storage import GZIPMixin, PipelineStorage
import re

STATIC_LOCATION = os.path.join(settings.BASE_DIR, 'staticfiles')


class MyLocalStaticFilesStorage(storage.StaticFilesStorage):

    def __init__(self, *args, **kwargs):
        kwargs['location'] = STATIC_LOCATION
        super().__init__(*args, **kwargs)


class GZIPCachedStorage(MyLocalStaticFilesStorage, PipelineStorage, GZIPMixin):
    """
    Django and django-pipeline does not make it easy to selectively remove files
    that you don't want collected so this is a hack until a better way is found.
    """
    gzip_patterns = ("*.css", "*.js", '*.png')
    whitelist_patterns = (
        'css/',
        'django_extensions/',
        'admin/',
        'debug_toolbar/',
        'images/',
        'js/emailcongress.min.js',
    )

    def post_process(self, paths, dry_run=False, **options):

        yield from super().post_process(paths, dry_run, **options)

        # deletes files not found in the whitelist patterns
        self._cleanup()

        # upload to S3 if requested
        # TODO

    def _cleanup(self):
        """
        Remove all files that don't match any of the whitelist patterns.

        @return:
        @rtype:
        """

        for root, dirs, files in os.walk(STATIC_LOCATION):

            for file in files:
                reldir = os.path.relpath(root, STATIC_LOCATION)
                relpath = os.path.join(reldir, file)
                delete = True
                for pattern in self.whitelist_patterns:
                    if re.search(pattern, relpath):
                        delete = False
                if delete:
                    full_file_path = os.path.join(root, file)
                    print("Deleting intermediate file '{0}'".format(full_file_path))
                    os.remove(full_file_path)

        for root, dirs, files in os.walk(STATIC_LOCATION, topdown=False):
            for name in dirs:
                directory = os.path.join(root, name)
                try:
                    if not os.listdir(directory): # to check if the dir is empty
                        print("Deleting empty directory '{0}'".format(directory))
                        os.removedirs(directory)
                except:
                    continue