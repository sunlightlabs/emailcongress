from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from emailcongress.models import User, UserMessageInfo, Token, Legislator, MessageLegislator, Message
from django.contrib.auth.models import User as DjangoUser
import abc


class AbstractAdmin(admin.ModelAdmin):
    __metaclass__ = abc.ABCMeta

    def get_list_display(self, request):
        return self.list_display + ('created_at', 'updated_at')


class UserAdmin(AbstractAdmin):

    list_display = ('django_user', )


class TokenAdmin(AbstractAdmin):

    list_display = ('object_id', 'key', 'content_type')


class LegislatorAdmin(AbstractAdmin):

    list_display = ('bioguide_id', 'title', 'first_name', 'last_name', 'chamber',
                    'state', 'district', 'email', 'contactable')
    search_fields = list_display


class MessageAdmin(AbstractAdmin):

    list_display = ('id', 'subject', 'msgbody', 'email_uid', 'status', 'user_message_info')
    search_fields = list_display


class UserMessageInfoAdmin(AbstractAdmin):

    list_display = ('user', 'default', 'prefix', 'first_name', 'last_name', 'zip5', 'state', 'district', 'accept_tos')
    search_fields = ('user__django_user__email', 'prefix', 'first_name',
                     'last_name', 'zip5', 'state', 'district', 'accept_tos')


class MessageLegislatorAdmin(admin.ModelAdmin):
    pass


class DjangoUserAdmin(BaseUserAdmin):

    search_fields = ['email']

    pass


admin.site.register(User, UserAdmin)
admin.site.register(Token, TokenAdmin)
admin.site.register(Legislator, LegislatorAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(UserMessageInfo, UserMessageInfoAdmin)
admin.site.register(MessageLegislator, MessageLegislatorAdmin)

admin.site.unregister(DjangoUser)
admin.site.register(DjangoUser, DjangoUserAdmin)
