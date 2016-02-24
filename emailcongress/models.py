import random
from datetime import datetime, timedelta
import uuid

from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from jsonfield import JSONField
from localflavor.us import models as us_models

from lib.phantom_on_the_capitol import PhantomOfTheCapitol
from lib import usps
from django.conf import settings
from services import determine_district_service, geolocation_service, address_inferrence_service


class EmailCongressManager(models.Manager):

    def get_or_instantiate(self, **kwargs):
        objs = self.filter(**kwargs)
        return objs if objs else self.model(**kwargs)


class EmailCongressModel(models.Model):

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EmailCongressManager()

    class Meta:
        abstract = True

    def serialize(self, to_format):
        return serializers.serialize(to_format, [self,])


class Token(EmailCongressModel):

    token = models.CharField(max_length=64, unique=True, null=True)
    object_id = models.PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    content_object = GenericForeignKey()

    @staticmethod
    def new_token_trigger(sender, instance, created, *args, **kwargs):
        if created:
            instance.token = instance.uid_creator()
            instance.save()

    @classmethod
    def uid_creator(cls):
        """
        Creates a 64 character string uid, checks for collisions in input class, and returns a uid.

        @return: 64 character alphanumeric string
        @rtype: string
        """
        while True:
            potential_token = uuid.uuid4().hex + uuid.uuid4().hex
            if cls.objects.filter(token=potential_token).count() == 0:
                return potential_token

    @classmethod
    def convert_token(cls, token):
        """
        Converts a token to user, the user's default information, and a message

        @return: tuple of message, user message info, and user
        @rtype: (Message, UserMessageInfo, User)
        """
        msg, umi, user = None, None, None
        token = cls.objects.filter(token=token).first()
        if token is not None:
            item = token.content_object
            if type(item) is User:
                user = item
                umi = user.default_info
            elif type(item) is Message:
                msg = item
                umi = msg.user_message_info
                user = umi.user

        return msg, umi, user

    def reset(self, token=None):
        self.token = token if token is not None else self.uid_creator()
        self.save()
        return self.token

    def link(self):
        pass
        # return app_router_path('update_user_address', token=self.token)

receiver(post_save, sender=Token, dispatch_uid='new_token')(Token.new_token_trigger)


class Legislator(EmailCongressModel):

    bioguide_id = models.CharField(max_length=7, unique=True, null=False)
    chamber = models.CharField(max_length=20)
    state = us_models.USStateField()
    district = models.IntegerField(null=True)
    title = models.CharField(max_length=3)
    first_name = models.CharField(max_length=256)
    last_name = models.CharField(max_length=256)
    contact_form = models.CharField(max_length=1024, null=True)
    oc_email = models.CharField(max_length=256)
    contactable = models.BooleanField(default=True)

    FIPS_CODES = {
        "AK": "02", "AL": "01", "AR": "05", "AS": "60", "AZ": "04", "CA": "06", "CO": "08", "CT": "09", "DC": "11",
        "DE": "10", "FL": "12", "GA": "13", "GU": "66", "HI": "15", "IA": "19", "ID": "16", "IL": "17", "IN": "18",
        "KS": "20", "KY": "21", "LA": "22", "MA": "25", "MD": "24", "ME": "23", "MI": "26", "MN": "27", "MO": "29",
        "MS": "28", "MT": "30", "NC": "37", "ND": "38", "NE": "31", "NH": "33", "NJ": "34", "NM": "35", "NV": "32",
        "NY": "36", "OH": "39", "OK": "40", "OR": "41", "PA": "42", "PR": "72", "RI": "44", "SC": "45", "SD": "46",
        "TN": "47", "TX": "48", "UT": "49", "VA": "51", "VI": "78", "VT": "50", "WA": "53", "WI": "55", "WV": "54",
        "WY": "56"
    }

    CONGRESS_API_COLUMNS = ['bioguide_id', 'chamber', 'state', 'district', 'title',
                            'first_name', 'last_name', 'contact_form', 'oc_email']

    @staticmethod
    def doctor_oc_email(email):
        """
        Converts an email string to an opencongress.org address by string replacement.

        @param email: the email to convert to an opencongress.org address
        @type email: str
        @return: converted email
        @rtype: str
        """
        return email.replace(settings.CONFIG_DICT['misc']['domain'], "opencongress.org")

    @staticmethod
    def find_by_recip_email(recip_email):
        return Legislator.objects.filter(oc_email__iexact=Legislator.doctor_oc_email(recip_email)).first()

    @classmethod
    def get_leg_buckets_from_emails(cls, permitted_legs, emails):
        legs = {label: [] for label in ['contactable','non_existent','uncontactable','does_not_represent']}
        inbound_emails = [email_addr for email_addr in emails]

        # user sent to catchall address
        if settings.CONFIG_DICT['email']['catch_all'] in inbound_emails:
            legs['contactable'] = permitted_legs
            inbound_emails.remove(settings.CONFIG_DICT['email']['catch_all'])
        elif Legislator.doctor_oc_email(settings.CONFIG_DICT['email']['catch_all']) in inbound_emails:
            legs['contactable'] = permitted_legs
            inbound_emails.remove(Legislator.doctor_oc_email(settings.CONFIG_DICT['email']['catch_all']))

        # maximize error messages for users for individual addresses
        for recip_email in inbound_emails:
            # IMPORTANT! OC_EMAIL is legacy from @opencongress.org. The new addresses are @emailcongress.us.
            leg = Legislator.find_by_recip_email(recip_email)
            if leg is None:
                legs['non_existent'].append(recip_email)  # TODO refer user to index page?
            elif not leg.contactable:
                legs['uncontactable'].append(leg)
            elif leg not in permitted_legs:
                legs['does_not_represent'].append(leg)
            elif leg not in legs['contactable']:
                legs['contactable'].append(leg)
            else:
                continue

        return legs


    """
    @staticmethod
    def find_by_recip_email(recip_email):
        return Legislator.query.filter(
            func.lower(Legislator.oc_email) == func.lower(Legislator.doctor_oc_email(recip_email))).first()

    @staticmethod
    def doctor_oc_email(email):
        return email.replace(settings.EMAIL_DOMAIN, "opencongress.org")

    @staticmethod
    def humanized_district(state, district):
        return (ordinal(int(district)) if int(district) > 0 else 'At-Large') + ' Congressional district of ' + usps.CODE_TO_STATE.get(state)

    @staticmethod
    def humanized_state(state):
        return usps.CODE_TO_STATE.get(state)

    @staticmethod
    def get_district_geojson_url(state, district):
        try:
            fips = Legislator.FIPS_CODES.get(state)
            return "http://realtime.influenceexplorer.com/geojson/cd113_geojson/%s%0*d.geojson" % (fips, 2, int(district))
        except:
            return None

    @classmethod
    def members_for_state_and_district(cls, state, district, contactable=None):
        or_seg = or_(Legislator.district.is_(None), Legislator.district == district)
        and_seg = [Legislator.state == state, or_seg]
        if contactable is not None:
            query = and_(Legislator.contactable.is_(contactable), *and_seg)
        else:
            query = and_(*and_seg)

        return Legislator.query.filter(query).all()

    @classmethod
    def congress_api_columns(cls):
        return [col.name for col in cls.__table__.columns if 'official' in col.info and col.info['official']]

    @classmethod
    def get_leg_buckets_from_emails(self, permitted_legs, emails):
        legs = {label: [] for label in ['contactable','non_existent','uncontactable','does_not_represent']}
        inbound_emails = [email_addr for email_addr in emails]

        # user sent to catchall address
        if settings.CATCH_ALL_MYREPS in inbound_emails:
            legs['contactable'] = permitted_legs
            inbound_emails.remove(settings.CATCH_ALL_MYREPS)
        elif Legislator.doctor_oc_email(settings.CATCH_ALL_MYREPS) in inbound_emails:
            legs['contactable'] = permitted_legs
            inbound_emails.remove(Legislator.doctor_oc_email(settings.CATCH_ALL_MYREPS))

        # maximize error messages for users for individual addresses
        for recip_email in inbound_emails:
            # IMPORTANT! OC_EMAIL is legacy from @opencongress.org. The new addresses are @emailcongress.us.
            leg = Legislator.find_by_recip_email(recip_email)
            if leg is None:
                legs['non_existent'].append(recip_email)  # TODO refer user to index page?
            elif not leg.contactable:
                legs['uncontactable'].append(leg)
            elif leg not in permitted_legs:
                legs['does_not_represent'].append(leg)
            elif leg not in legs['contactable']:
                legs['contactable'].append(leg)
            else:
                continue

        return legs

    def full_title(self):
        return {
            'Com': 'Commissioner',
            'Del': 'Delegate',
            'Rep': 'Representative',
            'Sen': 'Senator'
        }.get(self.title, 'Representative')

    def full_name(self):
        return self.first_name + " " + self.last_name

    def title_and_last_name(self):
        return self.title + " " + self.last_name

    def title_and_full_name(self):
        return self.title + " " + self.full_name()

    def full_title_and_full_name(self):
        return self.full_title() + " " + self.full_name()

    def image_url(self, size='small'):
        dimensions = {
            'small': '225x275',
            'large': '450x550'
        }
        return "https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/" + \
               dimensions.get(size, dimensions.values()[0]) + "/" + self.bioguide_id + '.jpg'

    @property
    def email(self):
        return self.oc_email.replace('opencongress.org', settings.EMAIL_DOMAIN)
    """


class User(EmailCongressModel):

    email = models.CharField(max_length=256, unique=True)
    token = GenericRelation(Token)

    @staticmethod
    def new_user_trigger(sender, instance, created, *args, **kwargs):
        if created:
            UserMessageInfo.objects.create(user=instance, default=True)
            Token.objects.create(content_object=instance)

    def messages(self, **filters):
        query = Q(**filters) & Q(user_message_info__in=self.usermessageinfo_set.all())
        return Message.objects.filter(query).order_by('created_at')

    def last_message(self):
        return self.messages().last()

    @property
    def default_info(self):
        return UserMessageInfo.objects.filter(user=self, default=True).first()

    def __html__(self):
        pass # return render_without_request('snippets/user.html', user=self)

    def new_address_change_link(self):
        self.token.reset()

    def get_rate_limit_status(self):

        count = self.messages().filter(created_at__gte=(datetime.now() -
                                       timedelta(hours=settings.CONFIG_DICT['email']['interval_hour_max']))).count()
        if count > settings.CONFIG_DICT['email']['max_per_interval']:
            return 'block'
        else:
            return 'free'


    """


    def get_rate_limit_status(self):

        if self.can_skip_rate_limit():
            return 'free'

        if User.global_captcha():
            return 'g_captcha'

        count = self.messages().filter((datetime.now() - timedelta(hours=settings.USER_MESSAGE_LIMIT_HOURS) < Message.created_at)).count()
        if count > settings.USER_MESSAGE_LIMIT_BLOCK_COUNT:
            return 'block'
        elif count > settings.USER_MESSAGE_LIMIT_CAPTCHA_COUNT:
            return 'captcha'
        else:
            return 'free'

    def new_address_change_link(self):
        self.token.reset()

    def address_change_link(self):
        return self.token.link()

    class Analytics(BaseAnalytics):

        def __init__(self):
            super(User.Analytics, self).__init__(User)

        def users_with_verified_districts(self):
            return UserMessageInfo.query.join(User).filter(
                and_(UserMessageInfo.default.is_(True), not_(UserMessageInfo.district.is_(None)))).count()

    """
receiver(post_save, sender=User, dispatch_uid='new_user')(User.new_user_trigger)


class UserMessageInfo(EmailCongressModel):

    user = models.ForeignKey(User)
    default = models.NullBooleanField(default=False)

    # input by user
    prefix = models.CharField(max_length=32, blank=False)
    first_name = models.CharField(max_length=256, blank=False)
    last_name = models.CharField(max_length=256, blank=False)
    street_address = models.CharField(max_length=1000, blank=False)
    street_address2 = models.CharField(max_length=1000, blank=True)
    city = models.CharField(max_length=256, blank=False)
    state = us_models.USStateField(blank=False)
    zip5 = models.CharField(max_length=5, blank=False)
    zip4 = models.CharField(max_length=4, blank=False)
    phone_number = models.CharField(max_length=20, blank=False)
    accept_tos = models.DateTimeField(default=None, null=True)

    # set by methods based on input address information above
    latitude = models.CharField(max_length=256, null=True)
    longitude = models.CharField(max_length=256, null=True)
    district = models.IntegerField(default=None, null=True)

    def confirm_accept_tos(self):
        self.accept_tos = datetime.now()
        self.save()

    def mailing_address(self):
        return self.street_address + ' ' + self.street_address2 + ', '\
               + self.city + ', ' + self.state + ' ' + self.zip5 + '-' + self.zip4

    def should_update_address_info(self):
        return self.accept_tos is None or \
               (datetime.now() - self.accept_tos).days >= settings.CONFIG_DICT['misc']['tos_days_valid']

    def geolocate_address(self, force=False):

        if force or (self.latitude is None and self.longitude is None):
            try:
                self.latitude, self.longitude = geolocation_service.geolocate(street_address=self.street_address,
                                                                              city=self.city,
                                                                              state=self.state,
                                                                              zip5=self.zip5)
                self.save()
                return self.latitude, self.longitude
            except:
                return None, None

    def determine_district(self, force=False):

        if not force and self.district is not None:
            return self.district

        data = determine_district_service.determine_district(zip5=self.zip5)
        if data is None:
            self.geolocate_address()
            data = determine_district_service.determine_district(latitude=self.latitude, longitude=self.longitude)
        try:
            self.district = data.get('district')
            self.state = data.get('state')
            self.save()
            return self.district
        except:
            print("Unable to determine district for " + self.mailing_address())
            return None

    @property
    def members_of_congress(self):
        if self.district is None:
            self.determine_district()
        query = Q(contactable=True) & Q(state=self.state) & (Q(district=None) | Q(district=self.district))
        return Legislator.objects.filter(query).all()


    """
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.comparable_attributes() == other.comparable_attributes()
        return False

    def comparable_attributes(self):
        return {key: value for key, value in self.__dict__ if key in self.user_input_columns()}

    @classmethod
    def first_or_create(cls, user_id, created_at=datetime.now, **kwargs):
        user = User.query.filter_by(id=user_id).first()
        if user is not None:
            sanitize_keys(kwargs, cls.user_input_columns())
            umi = UserMessageInfo.query.filter_by(**kwargs).first()
            if umi is not None: return umi
            else:
                created_at = parser.parse(created_at) if type(created_at) is str else created_at().replace(tzinfo=pytz.timezone('US/Eastern'))
                umi = UserMessageInfo(user_id=user.id, created_at=created_at, **kwargs)
                db_add_and_commit(umi)
                return umi

    @classmethod
    def user_input_columns(cls):
        return [col.name for col in cls.__table__.columns if 'user_input' in col.info and col.info['user_input']]

    def humanized_district(self):
        return Legislator.humanized_district(self.state, self.district)

    def humanized_state(self):
        return Legislator.humanized_state(self.state)

    def confirm_accept_tos(self):
        self.accept_tos = datetime.now()
        db.session.commit()

    def should_update_address_info(self):

        return self.accept_tos is None or (datetime.now() - self.accept_tos).days >= settings.ADDRESS_DAYS_VALID

    def mailing_address(self):
        return self.street_address + ' ' + self.street_address2 + ', '\
               + self.city + ', ' + self.state + ' ' + self.zip5 + '-' + self.zip4

    def complete_information(self):
        if self.district is None:
            self.determine_district(force=True)
        if not self.zip4:
            self.zip4_lookup(force=True)

    def zip4_lookup(self, force=False):
        if force or not self.zip4:
            try:
                self.zip4 = address_inferrence_service.zip4_lookup(self.street_address,
                                                                   self.city,
                                                                   self.state,
                                                                   self.zip5
                                                                   )
                db.session.commit()
            except:
                db.session.rollback()

    def geolocate_address(self, force=False):

        if force or (self.latitude is None and self.longitude is None):
            try:
                self.latitude, self.longitude = geolocation_service.geolocate(street_address=self.street_address,
                                                                              city=self.city,
                                                                              state=self.state,
                                                                              zip5=self.zip5)
                db.session.commit()
                return self.latitude, self.longitude
            except:
                return None, None

    def get_district_geojson_url(self):
        return Legislator.get_district_geojson_url(self.state, self.district)

    def determine_district(self, force=False):

        if not force and self.district is not None:
            return self.district

        data = determine_district_service.determine_district(zip5=self.zip5)
        if data is None:
            self.geolocate_address()
            data = determine_district_service.determine_district(latitude=self.latitude, longitude=self.longitude)

        try:
            self.district = data.get('district')
            self.state = data.get('state')
            db.session.commit()
            return self.district
        except:
            print "Unable to determine district for " + self.mailing_address()
            return None

    @property
    def members_of_congress(self):
        if self.district is None:
            self.determine_district()
        return Legislator.query.filter(
            and_(Legislator.contactable.is_(True), Legislator.state == self.state,
                 or_(Legislator.district.is_(None), Legislator.district == self.district))).all()

    """


class Message(EmailCongressModel):

    to_originally = models.CharField(max_length=8000)
    subject = models.CharField(max_length=500)
    msgbody = models.CharField(max_length=8000)
    email_uid = models.CharField(max_length=1000)
    status = models.CharField(max_length=10, null=True, default='free')
    user_message_info = models.ForeignKey(UserMessageInfo)

    def get_legislators(self, as_dict=False):

        if as_dict:
            return {leg.legislator.bioguide_id: leg for leg in self.legislatormessage_set.all()}
        else:
            return Legislator.objects.filter(id__in=self.legislatormessage_set.all().values_list('id', flatten=True))

    def has_legislators(self):
        return self.get_legislators()

    def set_legislators(self, legislators):

        if type(legislators) is not list:
            legislators = [legislators]

        try:
            to_set = [MessageLegislator.objects.get_or_create(message_id=self.id, legislator=leg)[0]
                      for leg in legislators]
            self.legislatormessage_set.set(to_set)
            return True
        except:
            return False


    def add_legislators(self, legislators):

        if type(legislators) is not list:
            legislators = [legislators]

        try:
            to_add = [MessageLegislator.objects.get_or_create(message_id=self.id, legislator=leg)[0]
                      for leg in legislators]
            self.legislatormessage_set.add(to_add)
            return True
        except:
            return False


    def is_free_to_send(self):
        return self.status == 'free'

    def update_status(self):
        self.status = self.user_message_info.user.get_rate_limit_status()
        self.save()

    def queue_to_send(self, moc=None):
        from emailcongress.scheduler import send_to_phantom_of_the_capitol
        self.status = None
        self.save()
        if moc is not None:
            self.set_legislators(moc)
        send_to_phantom_of_the_capitol.delay(msg_id=self.id, force=True)
        return True

    def send(self, fresh=False):

        newly_sent = []
        for msg_leg in self.legislatormessage_set.all():
            try:
                newly_sent.append(msg_leg.send())
            except:
                continue
        return newly_sent if fresh else self.legislatormessage_set.all()

    def map_to_contact_congress_fields(self):

        umi = self.user_message_info
        return {
            '$NAME_PREFIX': umi.prefix,
            '$NAME_FIRST': umi.first_name,
            '$NAME_LAST': umi.last_name,
            '$NAME_FULL': umi.first_name + ' ' + umi.last_name,
            '$ADDRESS_STREET': umi.street_address,
            '$ADDRESS_STREET_2': umi.street_address2,
            '$ADDRESS_CITY': umi.city,
            '$ADDRESS_ZIP5': umi.zip5,
            '$ADDRESS_ZIP4': umi.zip4,
            "$ADDRESS_ZIP_PLUS_4": umi.zip5 + '-' + umi.zip4,
            '$EMAIL': umi.user.email,
            '$SUBJECT': self.subject,
            '$MESSAGE': self.msgbody,
            '$ADDRESS_STATE_POSTAL_ABBREV': umi.state,
            '$PHONE': umi.phone_number,
            '$ADDRESS_STATE_FULL': usps.CODE_TO_STATE.get(umi.state)
        }


    """




    def get_send_status(self):
        target_count = len(self.to_legislators)
        sent_count = MessageLegislator.query.join(Message).filter(Message.id == self.id,
                                                                  MessageLegislator.sent.is_(True)).count()
        if sent_count == 0:
            return 'unsent'
        elif sent_count < target_count:
            return 'sundry'
        else:
            return 'sent'

    def associate_legislators(self, force=False):
        if force or not self.to_legislators:
            self.set_legislators(self.user_message_info.members_of_congress)

    def free_link(self):
        set_attributes(self, {'status': 'free'}.iteritems(), commit=True)

    def kill_link(self):
        set_attributes(self, {'status': None}.iteritems(), commit=True)

    def update_status(self):
        self.status = self.user_message_info.user.get_rate_limit_status()
        db.session.commit()

    def needs_captcha_to_send(self):
        return self.status in ['captcha', 'g_captcha']

    def is_free_to_send(self):
        return self.status == 'free'

    def is_already_sent(self):
        return self.status is None

    def queue_to_send(self, moc=None):
        from scheduler import send_to_phantom_of_the_capitol
        set_attributes(self, {'status': None}.iteritems(), commit=True)
        if moc is not None: self.set_legislators(moc)
        send_to_phantom_of_the_capitol.delay(msg_id=self.id, force=True)
        return True

    def send(self, fresh=False):

        newly_sent = []
        for msg_leg in self.to_legislators:
            try:
                newly_sent.append(msg_leg.send())
            except:
                continue
        return newly_sent if fresh else self.to_legislators

    def map_to_contact_congress_fields(self):

        umi = self.user_message_info
        return {
            '$NAME_PREFIX': umi.prefix,
            '$NAME_FIRST': umi.first_name,
            '$NAME_LAST': umi.last_name,
            '$NAME_FULL': umi.first_name + ' ' + umi.last_name,
            '$ADDRESS_STREET': umi.street_address,
            '$ADDRESS_STREET_2': umi.street_address2,
            '$ADDRESS_CITY': umi.city,
            '$ADDRESS_ZIP5': umi.zip5,
            '$ADDRESS_ZIP4': umi.zip4,
            "$ADDRESS_ZIP_PLUS_4": umi.zip5 + '-' + umi.zip4,
            '$EMAIL': umi.user.email,
            '$SUBJECT': self.subject,
            '$MESSAGE': self.msgbody,
            '$ADDRESS_STATE_POSTAL_ABBREV': umi.state,
            '$PHONE': umi.phone_number,
            '$ADDRESS_STATE_FULL': usps.CODE_TO_STATE.get(umi.state)
        }

    class Analytics():

        def __init__(self):
            super(Message.Analytics, self).__init__(Message)
    """


class MessageLegislator(EmailCongressModel):

    send_status = JSONField(max_length=8000, default={'status': 'unsent'})
    sent = models.NullBooleanField(default=None)
    message = models.ForeignKey(Message)
    legislator = models.ForeignKey(Legislator)

    def is_sent(self):
        return self.sent

    def send(self):
        """
        Method that actually passes information to phantom of the capitol.

        @return: self
        @rtype: models.MessageLegislator
        """
        if self.is_sent() is not True:

            phantom = PhantomOfTheCapitol(endpoint=settings.CONFIG_DICT['api_endpoints']['phantom_base'])

            for bioguide_id, ra in phantom.retrieve_form_elements([self.legislator.bioguide_id]).iteritems():
                json_dict = self.map_to_contact_congress()

                for step in ra['required_actions']:
                    field = step.get('value')
                    options = step.get('options_hash')
                    if options is not None:
                        # convert first to dictionary for convenience
                        if type(options) is not dict:
                            options = {k: k for k in options}
                        if field == '$TOPIC':
                            # TODO handle more sophisticated topic selection
                            # need lower case strings for select-solver
                            options = {k.lower(): v for k, v in options.items()}
                            try:  # try to determine best topic based off content of text
                                pass
                            except:  # if failed, choose a random topic
                                pass
                        if field not in json_dict['fields'] or json_dict['fields'][field] not in options.values():
                            json_dict['fields'][field] = random.choice(options.values())
                    if field not in json_dict['fields'].keys():
                        print('What the heck is ' + step.get('value') + ' in ' + bioguide_id + '?')
                result = phantom.fill_out_form(json_dict)
                self.sent = result['status'] == 'success'
                self.send_status = result
            self.save()
            return self

    def map_to_contact_congress(self, campaign_tag=False):
        data = {
            'bio_id': self.legislator.bioguide_id,
            'fields': self.message.map_to_contact_congress_fields()
        }
        if campaign_tag:
            data['campaign_tag'] = self.message.email_uid

        return data
