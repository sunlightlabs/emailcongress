import re
import datetime

from django.forms import ValidationError, ModelForm, TextInput, CharField, ChoiceField, EmailField, EmailInput
from django.template.loader import render_to_string
from django.core import validators
from django.forms.widgets import ChoiceInput
from django.forms.utils import ErrorList

from emailcongress.models import UserMessageInfo, DjangoUser, User


class UserMessageInfoForm(ModelForm):

    name_error_message = 'Unfortunately, many congressional forms only acccept English ' \
                         'alphabet names without spaces. Please enter a name using only ' \
                         'the English alphabet.'

    first_name = CharField(required=True,
                           widget=TextInput(
                               attrs={'class': 'form__input',
                                      'placeholder': 'First Name',
                                      'pattern': "[A-Za-z\s]{1,20}"}),
                           validators=[validators.RegexValidator(regex=r'[A-Za-z\s]{1,20}',
                                            message=name_error_message),
                                       validators.MaxLengthValidator(20),
                                       validators.MinLengthValidator(1)]
                           )

    last_name = CharField(required=True,
                           widget=TextInput(
                               attrs={'class': 'form__input',
                                      'placeholder': 'Last Name',
                                      'pattern': "[A-Za-z\s]{1,20}"}),
                           validators=[validators.RegexValidator(regex=r'[A-Za-z\s]{1,20}',
                                            message=name_error_message),
                                      validators.MinLengthValidator(1),
                                      validators.MaxLengthValidator(20)]
                           )

    street_address = CharField(required=True,
                               widget=TextInput(
                                   attrs={'class': 'form__input',
                                          'placeholder': 'Street Address'}),
                               validators=[validators.MinLengthValidator(1),
                                           validators.MaxLengthValidator(256)]
                               )

    street_address2 = CharField(required=False,
                           widget=TextInput(
                               attrs={'class': 'form__input',
                                      'placeholder': 'Apt/Suite'}),
                           validators=[validators.MinLengthValidator(1),
                                       validators.MaxLengthValidator(256)]
                           )

    city = CharField(required=True,
                       widget=TextInput(
                           attrs={'class': 'form__input',
                                  'placeholder': 'City'}),
                       validators=[validators.MinLengthValidator(1),
                                   validators.MaxLengthValidator(256)]
                       )

    zip = CharField(required=True,
                     widget=TextInput(
                           attrs={'class': 'form__input--masked',
                                  'placeholder': 'Zipcode'}),
                       validators=[validators.RegexValidator(regex=r'^\d{5}-\d{4}$',
                                         message='Zipcode and Zip+4 must have form XXXXX-XXXX. Lookup up <a target="_blank" href="https://tools.usps.com/go/ZipLookupAction!input.action">here</a>')]
                       )

    phone_number = CharField(required=True,
                      widget=TextInput(
                          attrs={'class': 'form__input--masked',
                                 'placeholder': 'Phone Number',}),
                      validators=[validators.RegexValidator(regex=r'^\([0-9]{3}\) [0-9]{3}-[0-9]{4}$',
                                        message='Please enter a phone number with format (XXX) XXX-XXXX')]
                      )

    email = EmailField(required=True,
                  widget=EmailInput(
                      attrs={'class': 'form__input',
                             'placeholder': 'E-mail'}),
                  error_messages={'invalid': 'Please enter a valid email address.'}
                  )

    class Meta:
        model = UserMessageInfo
        fields = ['prefix', 'first_name', 'last_name', 'street_address', 'street_address2',
                  'city', 'state', 'phone_number', 'email']

    def __str__(self):
        return render_to_string('www/forms/address_form.html', context={'form': self})

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if DjangoUser.objects.filter(email=email).exists():
            raise ValidationError("Email already exists") # TODO handle case where user previously signed up and forgot or malicious signups
        return email

    def clean_phone_number(self):
        return re.sub("[^0-9]", "", self.cleaned_data.get('phone_number'))

    def clean_first_name(self):
        return self.cleaned_data.get('first_name').replace(' ', '')

    def clean_last_name(self):
        return self.cleaned_data.get('last_name').replace(' ', '')

    def clean_zip(self):
        zipdata = self.cleaned_data.get('zip').split('-')
        self.instance.zip5 = zipdata[0]
        self.instance.zip4 = zipdata[1]
        return zipdata

    def _post_clean(self):
        """
        We need the model instance created before we can determine the district.
        """
        super()._post_clean()
        try:
            self.instance.determine_district()
        except:
            error_msg = 'Unable to determine your congressional district from your zip code ' \
                        'and/or address. Please check again that your address information is ' \
                        'correct and try again. If this problem persists then please ' \
                        'contact us <a href="mailto:labs@sunlightfoundation.com">here</a>. '\
                        'You may also check to see if the government is able to determine ' \
                        'your congressional district ' \
                        '<a target="_blank" href="https://www.house.gov/representatives/find/">here</a>.'
            self.add_error(None, ValidationError(error_msg))
            # TODO robust error logging

    def save(self, commit=True):
        django_user = DjangoUser.objects.create_user(username=self.data['email'],
                                                     email=self.data['email'],
                                                     password='test')
        user, created = User.objects.get_or_create(django_user=django_user)

        self.instance.user = user
        self.instance.default = True

        super().save(commit=commit)
        return django_user
