from django.conf import settings
from lib import geocoder


def geolocate(**kwargs):
    try:
        geo = geocoder.Geocoder('TexasAm', {'apiKey': settings.CONFIG_DICT['api_keys']['texas_am']})
        geo.lookup(**kwargs)
        return geo.lat_long()
    except KeyError:
        raise


def reverse_geolocate(lat, lng):
    try:
        geo = geocoder.Geocoder('TexasAm', {'apiKey': settings.CONFIG_DICT['api_keys']['texas_am']})
        return geo.reverse_lookup(lat, lng)
    except KeyError:
        raise