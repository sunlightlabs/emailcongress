from django.contrib.staticfiles import storage
import os
from django.conf import settings
import re


from django.contrib.staticfiles import finders
from django.conf import settings


from django.contrib.staticfiles.storage import ManifestFilesMixin
from storages.backends.s3boto import S3BotoStorage

STATIC_LOCATION = os.path.join(settings.BASE_DIR, 'staticfiles')


class MyS3BotoStorage(ManifestFilesMixin, S3BotoStorage):

    pass


class MyStaticFilesStorage(storage.StaticFilesStorage):

    def __init__(self, *args, **kwargs):
        kwargs['location'] = STATIC_LOCATION
        super().__init__(*args, **kwargs)


def add_ignores(ignore_patterns):
    ignore = settings.STATICFILES_FINDERS_IGNORE

    if ignore:
        if ignore_patterns:
            ignore_patterns.extend(ignore)
        else:
            ignore_patterns = ignore

    return ignore_patterns


class FileSystemFinderIgnore(finders.FileSystemFinder):

    def list(self, ignore_patterns):
        return super().list(add_ignores(ignore_patterns))


class AppDirectoriesFinderIgnore(finders.AppDirectoriesFinder):

    def list(self, ignore_patterns):
        return super().list(add_ignores(ignore_patterns))


class DefaultStorageFinderIgnore(finders.DefaultStorageFinder):

    def list(self, ignore_patterns):
        return super().list(add_ignores(ignore_patterns))
