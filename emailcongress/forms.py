import re
import datetime

from django.forms import Form, ValidationError, ModelForm, TextInput, CharField, ChoiceField, EmailField, EmailInput
from django.template.loader import render_to_string
from django.core import validators
from django.forms.widgets import ChoiceInput
from django.forms.utils import ErrorList
from django.db import transaction

from emailcongress.models import UserMessageInfo, DjangoUser, User

from django import forms


class EmailForm(Form):

    email = EmailField(required=True,
                       widget=EmailInput(
                           attrs={'class': 'form__input',
                                  'placeholder': 'E-mail',
                                  'required': ''}),
                       error_messages={'invalid': 'Please enter a valid email address.'})

    submit_type = ChoiceField(required=True,
                              choices=(('update_address', 'update_address'),
                                       ('remind_reps', 'remind_reps')))

    def __str__(self):
        return render_to_string('www/forms/email_form.html', context={'form': self})


class UserMessageInfoForm(ModelForm):

    name_error_message = 'Unfortunately, many congressional forms only acccept English ' \
                         'alphabet names without spaces. Please enter a name using only ' \
                         'the English alphabet.'

    first_name = CharField(required=True,
                           widget=TextInput(
                               attrs={'class': 'form__input',
                                      'placeholder': 'First Name',
                                      'pattern': "[A-Za-z\s]{1,20}",
                                      'required': ''}),
                           validators=[validators.RegexValidator(regex=r'[A-Za-z\s]{1,20}',
                                            message=name_error_message),
                                       validators.MaxLengthValidator(20),
                                       validators.MinLengthValidator(1)]
                           )

    last_name = CharField(required=True,
                           widget=TextInput(
                               attrs={'class': 'form__input',
                                      'placeholder': 'Last Name',
                                      'pattern': "[A-Za-z\s]{1,20}",
                                      'required': ''}),
                           validators=[validators.RegexValidator(regex=r'[A-Za-z\s]{1,20}',
                                            message=name_error_message),
                                      validators.MinLengthValidator(1),
                                      validators.MaxLengthValidator(20)]
                           )

    street_address = CharField(required=True,
                               widget=TextInput(
                                   attrs={'class': 'form__input autofill__group',
                                          'placeholder': 'Street Address',
                                          'required': ''}),
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
                           attrs={'class': 'form__input autofill__group',
                                  'placeholder': 'City',
                                  'required': ''}),
                       validators=[validators.MinLengthValidator(1),
                                   validators.MaxLengthValidator(256)]
                       )

    zip = CharField(required=True,
                     widget=TextInput(
                           attrs={'class': 'form__input--masked autofill__group',
                                  'placeholder': 'Zipcode',
                                  'required': ''}),
                       validators=[validators.RegexValidator(regex=r'^\d{5}-\d{4}$',
                                         message='Zipcode and Zip+4 must have form XXXXX-XXXX. Lookup up <a target="_blank" href="https://tools.usps.com/go/ZipLookupAction!input.action">here</a>')]
                       )

    phone_number = CharField(required=True,
                      widget=TextInput(
                          attrs={'class': 'form__input--masked',
                                 'placeholder': 'Phone Number',
                                 'required': ''}),
                      validators=[validators.RegexValidator(regex=r'^\([0-9]{3}\) [0-9]{3}-[0-9]{4}$',
                                        message='Please enter a phone number with format (XXX) XXX-XXXX')]
                      )

    email = EmailField(required=True,
                  widget=EmailInput(
                      attrs={'class': 'form__input',
                             'placeholder': 'E-mail',
                             'required': ''}),
                  error_messages={'invalid': 'Please enter a valid email address.'}
                  )

    class Meta:
        model = UserMessageInfo
        fields = ['prefix', 'first_name', 'last_name', 'street_address', 'street_address2',
                  'city', 'state', 'phone_number', 'email']

    def __str__(self):
        return render_to_string('www/forms/address_form.html', context={'form': self})

    def disable_email_input(self):
        self['email'].field.widget.attrs['disabled'] = True

    def is_valid_with_original_email(self, email):
        if email != self.data.get('email'):
            error_msg = "E-mail must match the address that you originally sent your message from. Our records " \
                        "indicate that you sent your message from {0} but you've inputted {1} in this form. Please " \
                        "change it back to {0} if you wish to proceed or send your message from from " \
                        "{1}.".format(email, self.data.get('email'))
            self.add_error('email', ValidationError(error_msg))
        return self.is_valid()

    def clean_email(self):
        email = self.cleaned_data.get('email')
        try:
            if DjangoUser.objects.get(email=email).user.default_info.accept_tos is not None:
                error_msg = "The email you entered already exists in our system. " \
                            "Click here if you wish to update your address information or be reminded " \
                            "of your members of congress."
                self.add_error('email', ValidationError(error_msg))
        except:
            pass
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

    @transaction.atomic
    def save(self, commit=True):
        django_user, created = DjangoUser.objects.get_or_create(username=self.data['email'], email=self.data['email'])
        user, created = User.objects.get_or_create(django_user=django_user)
        user.usermessageinfo_set.update(default=False)
        self.instance.user = user
        self.instance.default = True
        super().save(commit=commit)
        return user.django_user

