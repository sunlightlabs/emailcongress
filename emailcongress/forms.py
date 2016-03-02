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
                      validators=[validators.RegexValidator(regex=r'^\(\d{3}\) \d{3}-\d{4}$',
                                        message='Please enter a phone number with format (XXX) XXX-XXXX')]
                      )

    email = EmailField(required=True,
                  widget=EmailInput(
                      attrs={'class': 'form__input',
                             'placeholder': 'E-mail'}),
                  )

    class Meta:
        model = UserMessageInfo
        fields = ['prefix', 'first_name', 'last_name', 'street_address', 'street_address2',
                  'city', 'state', 'phone_number', 'email']

    def __str__(self):
        return render_to_string('www/forms/address_form.html', context={'form': self})

    def clean_email(self):
        email = self.cleaned_data['email']
        if DjangoUser.objects.filter(email=email).exists():
            raise ValidationError("Email already exists")
        return email

    def save(self, commit=True):
        django_user = DjangoUser.objects.create_user(username=self.data['email'],
                                                     email=self.data['email'],
                                                     password='test')
        user, created = User.objects.get_or_create(django_user=django_user)

        self.instance.user = user
        self.instance.default = True
        self._autocomplete_zip()
        self._autocomplete_phone()
        self._doctor_names()

        self.instance.accept_tos = datetime.datetime.now()
        self.instance.determine_district()

        super().save(commit=commit)
        return django_user

    def _autocomplete_zip(self):
        zipdata = self.data['zip'].split('-')
        self.instance.zip5 = zipdata[0]
        self.instance.zip4 = zipdata[1]

    def _autocomplete_phone(self):
        self.instance.phone_number = re.sub("[^0-9]", "", self.instance.phone_number)

    def _doctor_names(self):
        self.instance.first_name = self.instance.first_name.replace(' ', '')
        self.instance.last_name = self.instance.last_name.replace(' ', '')
