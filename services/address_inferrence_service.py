from lib.usps import USPSScraper
from services.geolocation_service import geolocate, reverse_geolocate


def address_lookup(**kwargs):

    try:
        address = USPSScraper.usps_address_lookup(**kwargs)
        if address['city'] is not '' and address['state'] is not '':
            return address
        lat, lng = geolocate(**kwargs)
        return reverse_geolocate(lat, lng).address()
    except:
        return None


def zip4_lookup(street_address, city, state, zip5=''):
    # First try usps lookup because it doesn't eat up geolocation credits
    try:
        zip5, zip4 = USPSScraper.usps_zip_lookup(street_address, city, state, zip5)
        if zip4 is not None:
            return zip4
    except:
        # TODO proper error handling
        print("Error scraping from USPS ... moving on to geocoding")

    # If USPS is unable to determine zip4 then use geolocation method
    try:
        lat, lng = geolocate(street_address=street_address, city=city, state=state, zip5=zip5)
        return reverse_geolocate(lat, lng).zip4()
    except:
        # Give up. User must enter in their zip4 manually. #TODO proper error handling
        return None