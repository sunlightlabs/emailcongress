from django.conf import settings
from lib import geocoder


def geolocate(**kwargs):
    try:
        geo = geocoder.Geocoder('TexasAm', {'apiKey': settings.CONFIG_DICT['api_keys']['texas_am']})
        geo.lookup(**kwargs)
        return geo.lat_long()
    except KeyError:
        raise
        # TODO robust error handling


def reverse_geolocate(lat, lng, state=''):
    try:
        geo = geocoder.Geocoder('TexasAm', {'apiKey': settings.CONFIG_DICT['api_keys']['texas_am']})
        geo.reverse_lookup(lat, lng, state=state)
        return geo.address()
    except KeyError:
        raise
        # TODO robust error handling
