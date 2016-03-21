import random
from datetime import datetime, timedelta
import uuid

from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core import serializers
from django.db.models.signals import post_save, pre_save, pre_delete, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User as DjangoUser
from django.core.urlresolvers import reverse
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from jsonfield import JSONField
from localflavor.us import models as us_models

from lib.phantom_on_the_capitol import PhantomOfTheCapitol
from lib import usps
from services import determine_district_service, geolocation_service, address_inferrence_service
from emailcongress import utils
from emailcongress.celery import send_to_phantom_of_the_capitol


class EmailCongressManager(models.Manager):

    def get_or_instantiate(self, **kwargs):
        """
        Allows us to check for whether an object exists and if not instantiate it (without saving to database).

        @param kwargs:
        @type kwargs:
        @return:
        @rtype:
        """
        obj = self.filter(**kwargs).first()
        return obj if obj else self.model(**kwargs)


class TokenManager(EmailCongressManager):

    def select_related(self, *fields):
        """
        This is a hack because select_related doesn't work for GenericForeignKey and
        we need to scrub selected_related("user") reference from from rest_framework.authentication.TokenAuthentication
        See: http://stackoverflow.com/a/31319167

        @param fields: fields to select_related
        @type fields: tuple
        @return:
        @rtype:
        """
        return super().prefetch_related('content_object')


class EmailCongressModel(models.Model):

    class Meta:
        abstract = True

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EmailCongressManager()

    def serialize(self, to_format):
        return serializers.serialize(to_format, [self,])


class Token(EmailCongressModel):

    class Meta:
        permissions = (
            ("api", "Can access the API."),
        )

    key = models.CharField(max_length=64, unique=True, null=True, db_index=True)
    object_id = models.PositiveIntegerField(db_index=True)
    content_type = models.ForeignKey(ContentType, db_index=True)
    content_object = GenericForeignKey()

    objects = TokenManager()

    def __str__(self):
        return self.key

    @property
    def user(self):
        """
        Convenience method for getting the django auth user from this Token if it exists.

        @return: the django auth user or None
        @rtype: (DjangoUser|None)
        """
        if type(self.content_object) == User:
            return self.content_object.django_user
        else:
            return None

    def save(self, *args, **kwargs):
        """
        Generates a key if one doesn't exist before saving the token.
        """
        if not self.key:
            self.key = self.uid_creator()
        super().save(*args, **kwargs)

    def reset(self, key=None):
        self.key = key if key is not None else self.uid_creator()
        self.save()
        return self.key

    def link(self):
        return utils.construct_link(settings.PROTOCOL,
                                    settings.HOSTNAME,
                                    reverse('validate', kwargs={'token': self.key}))

    @classmethod
    def uid_creator(cls):
        """
        Creates a 64 character string uid, checks for collisions in input class, and returns a uid.

        @return: 64 character alphanumeric string
        @rtype: str
        """
        while True:
            potential_token = uuid.uuid4().hex + uuid.uuid4().hex
            if cls.objects.filter(key=potential_token).count() == 0:
                return potential_token

    @classmethod
    def convert_token(cls, key):
        """
        Converts a token to user, the user's default information, and a message.

        @param key: the string key to convert to other models
        @type key: str
        @return: tuple of message, user message info, and user
        @rtype: (Message, UserMessageInfo, User)
        """
        msg, umi, user = None, None, None
        token = cls.objects.filter(key=key).first()

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

    @staticmethod
    def delete_content_object(sender, instance, **kwargs):
        try:
            instance.content_object.delete()
        except:
            pass

receiver(post_delete, sender=Token)(Token.delete_content_object)


class HasTokenMixin(object):

    @property
    def verification_link(self):
        ctype = ContentType.objects.get_for_model(self)
        return Token.objects.get(content_type=ctype, object_id=self.pk).link()

    @property
    def token_key(self):
        ctype = ContentType.objects.get_for_model(self)
        return Token.objects.get(content_type=ctype, object_id=self.pk).key

    @staticmethod
    def create_token_trigger(sender, instance, created, *args, **kwargs):
        if created:
            ctype = ContentType.objects.get_for_model(instance)
            Token.objects.get_or_create(content_type=ctype, object_id=instance.pk)

    @staticmethod
    def delete_related_token(sender, instance, **kwargs):
        ctype = ContentType.objects.get_for_model(instance)
        Token.objects.filter(content_type=ctype, object_id=instance.pk).delete()


class Legislator(EmailCongressModel):

    bioguide_id = models.CharField(max_length=7, unique=True, null=False, db_index=True)
    chamber = models.CharField(max_length=20, db_index=True)
    state = us_models.USStateField(db_index=True)
    district = models.IntegerField(null=True, db_index=True)
    title = models.CharField(max_length=3, db_index=True)
    first_name = models.CharField(max_length=256, db_index=True)
    last_name = models.CharField(max_length=256, db_index=True)
    contact_form = models.CharField(max_length=1024, null=True, db_index=True)
    email = models.CharField(max_length=256, db_index=True)
    contactable = models.BooleanField(default=True, db_index=True)

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
                            'first_name', 'last_name', 'contact_form']

    def __str__(self):
        return "{0} {1} {2}".format(self.title, self.first_name, self.last_name)

    @property
    def full_title(self):
        return {
            'Com': 'Commissioner',
            'Del': 'Delegate',
            'Rep': 'Representative',
            'Sen': 'Senator'
        }.get(self.title, 'Representative')

    @property
    def full_name(self):
        return "{0} {1}".format(self.first_name, self.last_name)

    @property
    def title_and_last_name(self):
        return "{0} {1}".format(self.title, self.last_name)

    @property
    def title_and_full_name(self):
        return "{0} {1}".format(self.title, self.full_name)

    @property
    def full_title_and_full_name(self):
        return "{0} {1}".format(self.full_title, self.full_name)

    @property
    def image_url(self, size='small'):
        dimensions = {
            'small': '225x275',
            'large': '450x550'
        }
        return "https://raw.githubusercontent.com/unitedstates/images/gh-pages/congress/{0}/{1}.jpg".format(
            dimensions.get(size, dimensions['small']), self.bioguide_id
        )

    def create_email_address(self):
        raise NotImplementedError # TODO

    @staticmethod
    def humanized_district(state, district):
        d = '{0} Congressional district'.format(utils.ordinal(district) if int(district) > 0 else 'At-Large')
        if state:
            d += ' of {0}'.format(usps.CODE_TO_STATE.get(state))
        return d

    @property
    def humanized_constituency(self):
        return Legislator.humanized_district(self.state, self.district)

    @staticmethod
    def humanized_state(state):
        return usps.CODE_TO_STATE.get(state)

    @staticmethod
    def get_district_geojson_url(state, district):
        try:
            fips = Legislator.FIPS_CODES.get(state, "")
            return "http://realtime.influenceexplorer.com/geojson/cd113_geojson/%s%0*d.geojson" % (fips, 2, int(district))
        except:
            return ""

    @staticmethod
    def doctor_email(email):
        """
        Converts an email string to an opencongress.org address by string replacement.

        @param email: the email to convert to an opencongress.org address
        @type email: str
        @return: converted email
        @rtype: str
        """
        return email.replace("opencongress.org", settings.CONFIG_DICT['email']['domain'])

    @staticmethod
    def find_by_email(recip_email):
        return Legislator.objects.filter(email__iexact=Legislator.doctor_email(recip_email)).first()

    @staticmethod
    def get_leg_buckets_from_emails(permitted_legs, emails):
        """
        Retrieves

        @param permitted_legs:
        @type permitted_legs:
        @param emails:
        @type emails:
        @return: dictionary containing the various states of legislators to a user
        @rtype: dict[str, list]
        """
        legs = {label: [] for label in ['contactable','non_existent','uncontactable','does_not_represent']}
        inbound_emails = [email_addr for email_addr in emails]

        catch_all = [x for x in inbound_emails if settings.CONFIG_DICT['email']['catch_all'] in x]
        if catch_all:
            legs['contactable'] = permitted_legs
            for email in catch_all:
                inbound_emails.remove(email)

        # maximize error messages for users for individual addresses
        for recip_email in inbound_emails:
            # IMPORTANT! OC_EMAIL is legacy from @opencongress.org. The new addresses are @emailcongress.us.
            leg = Legislator.find_by_email(recip_email)
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

    @staticmethod
    def members_for_state_and_district(state, district, contactable=True):
        query = Q(state=state) & (Q(district=None) | Q(district=district))
        if contactable:
            query = query & Q(contactable=True)
        return Legislator.objects.filter(query).all()


class User(EmailCongressModel, HasTokenMixin):

    token = GenericRelation(Token, db_index=True)
    django_user = models.OneToOneField(DjangoUser, on_delete=models.CASCADE, db_index=True)

    def __str__(self):
        return self.django_user.email

    @property
    def default_info(self):
        return self.usermessageinfo_set.filter(default=True).first()

    @property
    def members_of_congress(self):
        return self.default_info.members_of_congress

    @property
    def email(self):
        return self.django_user.email

    @property
    def address_change_link(self):
        return self.token.get().link()

    def messages(self, **filters):
        query = Q(**filters) & Q(user_message_info__in=self.usermessageinfo_set.all())
        return Message.objects.filter(query).order_by('created_at')

    def last_message(self):
        return self.messages().last()

    def new_address_change_link(self):
        self.token.reset()

    def get_rate_limit_status(self, force_allow=False):
        """
        Determines whether this user is allowed to send any more messages.

        @param force_allow: whether to force allowance of sending
        @type force_allow: bool
        @return: string to represent whether to allow user to send more messages
        @rtype: str
        """
        count = self.messages().filter(created_at__gte=(timezone.now() -
                                       timedelta(hours=settings.CONFIG_DICT['email']['interval_hour_max']))).count()
        if count > settings.CONFIG_DICT['email']['max_per_interval'] and not force_allow:
            return 'block'
        else:
            return 'free'

    @staticmethod
    def delete_django_user(sender, instance, **kwargs):
        try:
            instance.django_user.delete()
        except:
            pass

    @staticmethod
    def get_or_create_user_from_email(email):
        try:
            with transaction.atomic():
                django_user, created = DjangoUser.objects.get_or_create(username=email, email=email)
                user, created = User.objects.get_or_create(django_user=django_user)
                if user.default_info and user.default_info.accept_tos:
                    umi = user.default_info
                else:
                    UserMessageInfo.objects.filter(user=user).update(default=False)
                    umi = UserMessageInfo.objects.create(user=user, default=True)
                return django_user, user, umi
        except IntegrityError:
            raise IntegrityError
            # TODO more robust error handling

receiver(post_delete, sender=User)(User.delete_django_user)
receiver(pre_delete, sender=User)(User.delete_related_token)
receiver(post_save, sender=User)(User.create_token_trigger)


class UserMessageInfo(EmailCongressModel):

    user = models.ForeignKey(User, db_index=True)
    default = models.NullBooleanField(default=False)

    PREFIX_CHOICES = (
        ('Mr.', 'Mr.'),
        ('Mrs.', 'Mrs.'),
        ('Ms.', "Ms.")
    )

    # input by user
    prefix = models.CharField(max_length=32, blank=False, choices=PREFIX_CHOICES)
    first_name = models.CharField(max_length=256, blank=False)
    last_name = models.CharField(max_length=256, blank=False)
    street_address = models.CharField(max_length=1000, blank=False)
    street_address2 = models.CharField(max_length=1000, blank=True, null=True)
    city = models.CharField(max_length=256, blank=False)
    state = us_models.USStateField(blank=False)
    zip5 = models.CharField(max_length=5, blank=False)
    zip4 = models.CharField(max_length=4, blank=False)
    phone_number = models.CharField(max_length=20, blank=False)
    accept_tos = models.DateTimeField(null=True)

    # set by methods based on input address information above
    latitude = models.CharField(max_length=256, blank=True, null=True)
    longitude = models.CharField(max_length=256, blank=True, null=True)
    district = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return "{0} {1}".format(self.first_name, self.last_name)

    @property
    def members_of_congress(self):
        if self.district is None:
            self.determine_district()
        return Legislator.members_for_state_and_district(self.state, self.district).order_by('title')

    @property
    def humanized_district(self):
        return Legislator.humanized_district(self.state, self.district)

    @property
    def humanized_district_no_state(self):
        return Legislator.humanized_district(None, self.district)

    @property
    def humanized_state(self):
        return Legislator.humanized_state(self.state)

    def confirm_accept_tos(self):
        self.accept_tos = timezone.now()
        self.save()

    def mailing_address(self):
        return "{0} {1}, {2}, {3} {4}-{5}".format(self.street_address, self.street_address2,
                                                  self.city, self.state, self.zip5, self.zip4)

    def must_update_address_info(self):
        return self.accept_tos is None or (timezone.now() - self.accept_tos).days >= settings.DAYS_TOS_VALID

    def complete_information(self):
        if self.district is None:
            self.determine_district()
        if not self.zip4:
            self.zip4_lookup(force=True)

    def geolocate_address(self, force=False, save=False):

        if force or (self.latitude is None or self.longitude is None):
            try:
                self.latitude, self.longitude = geolocation_service.geolocate(street_address=self.street_address,
                                                                              city=self.city,
                                                                              state=self.state,
                                                                              zip5=self.zip5)
                if save:
                    self.save()
                return self.latitude, self.longitude
            except:
                raise

    def determine_district(self, save=False):
        data = determine_district_service.determine_district(zip5=self.zip5)
        if data is None:
            lat, lng = self.geolocate_address()
            data = determine_district_service.determine_district(latitude=lat, longitude=lng)
        try:
            self.district = data.get('district')
            self.state = data.get('state')
            if save:
                self.save()
            return self.district
        except:
            return None # TODO robust error handling

    def zip4_lookup(self, force=False):
        if force or not self.zip4:
            try:
                zip4 = address_inferrence_service.zip4_lookup(self.street_address, self.city, self.state, self.zip5)
                self.update(zip4=zip4)
            except:
                pass

    def get_district_geojson_url(self):
        return Legislator.get_district_geojson_url(self.state, self.district)

    def clone_instance_for_address_update(self):
        """
        By setting pk to None then saving will create a new record.

        @return: None
        @rtype: None
        """
        self.pk = None
        self.updating = True
        self.accept_tos = None


class Message(EmailCongressModel, HasTokenMixin):

    token = GenericRelation(Token, db_index=True)

    to_originally = JSONField(max_length=8000)
    subject = models.CharField(max_length=500)
    msgbody = models.CharField(max_length=8000)
    email_uid = models.CharField(max_length=1000)
    status = models.CharField(max_length=10, null=True, default='free')
    user_message_info = models.ForeignKey(UserMessageInfo)

    def __str__(self):
        return "[{0}] {1}".format(self.id, self.subject[:25])

    @property
    def to_legislators(self):
        return self.messagelegislator_set.all()

    @property
    def has_legislators(self):
        return self.messagelegislator_set.count() > 0

    @property
    def legislators(self):
        return self.get_legislators()

    def get_legislators(self, as_dict=False):
        if as_dict:
            return {leg.legislator.bioguide_id: leg for leg in self.messagelegislator_set.all()}
        else:
            return [ml.legislator for ml in self.messagelegislator_set.all()]

    def generate_message_legislators(self, legislators):
        if type(legislators) is not list:
            legislators = list(legislators)
        return [MessageLegislator.objects.get_or_create(message_id=self.id, legislator=leg)[0] for leg in legislators]

    def set_legislators(self, legislators):
        MessageLegislator.objects.filter(message_id=self.id).delete()
        self.messagelegislator_set.set(self.generate_message_legislators(legislators))

    def add_legislators(self, legislators):
        self.messagelegislator_set.add(self.generate_message_legislators(legislators))

    def is_free_to_send(self):
        return self.status == 'free'

    def update_status(self):
        self.status = self.user_message_info.user.get_rate_limit_status()
        self.save()

    def free_status(self):
        self.status = 'free'
        self.save()

    def block_status(self):
        self.status = 'block'
        self.save()

    def get_send_status(self):
        target_count = self.to_legislators.count()
        sent_count = MessageLegislator.objects.filter(message=self, sent=True).count()
        if target_count == sent_count:
            return 'sent'
        elif sent_count == 0:
            return 'unsent'
        else:
            return '{0}/{1} sent'.format(str(sent_count), str(target_count))

    def queue_to_send(self, moc=None):
        if moc is not None:
            self.set_legislators(moc)
        send_to_phantom_of_the_capitol.delay(msg_id=self.id)

    def send(self, fresh=False):
        newly_sent = []
        for msg_leg in self.messagelegislator_set.all():
            try:
                newly_sent.append(msg_leg.send())
            except:
                continue
        return newly_sent if fresh else self.messagelegislator_set.all()

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
            '$ADDRESS_STATE_FULL': str(usps.CODE_TO_STATE.get(umi.state))
        }

receiver(pre_delete, sender=Message)(Message.delete_related_token)
receiver(post_save, sender=Message)(Message.create_token_trigger)


class MessageLegislator(EmailCongressModel):

    send_status = JSONField(max_length=8000, default={'status': 'unsent'})
    sent = models.NullBooleanField(default=None)
    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    legislator = models.ForeignKey(Legislator, null=True)

    def __str__(self):
        return "{0} -> {1}".format(self.message, self.legislator)

    def is_sent(self):
        return self.sent not in [None, False]

    def send(self):
        """
        Method that actually passes information to phantom of the capitol to send.

        @return: instance of this message to the legislator
        @rtype: MessageLegislator
        """
        if not self.is_sent():

            phantom = PhantomOfTheCapitol(endpoint=settings.CONFIG_DICT['api_endpoints']['phantom_base'])

            for bioguide_id, ra in phantom.retrieve_form_elements([self.legislator.bioguide_id]).items():
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

                        if field not in json_dict['fields'] or json_dict['fields'][field] not in options.values():
                            json_dict['fields'][field] = random.choice(list(options.values()))
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
