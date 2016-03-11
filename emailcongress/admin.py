from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from emailcongress.models import User, UserMessageInfo, Token, Legislator, MessageLegislator, UserMessageInfo, Message
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


class MessageAdmin(AbstractAdmin):

    list_display = ('id', 'subject', 'msgbody', 'email_uid', 'status', 'user_message_info')


class UserMessageInfoAdmin(AbstractAdmin):

    list_display = ('id', 'user', 'prefix', 'first_name', 'last_name', 'zip5', 'state', 'district')


class MessageLegislatorAdmin(admin.ModelAdmin):
    pass


class DjangoUserAdmin(BaseUserAdmin):
    pass


admin.site.register(User, UserAdmin)
admin.site.register(Token, TokenAdmin)
admin.site.register(Legislator, LegislatorAdmin)
admin.site.register(Message, MessageAdmin)
admin.site.register(UserMessageInfo, UserMessageInfoAdmin)
admin.site.register(MessageLegislator, MessageLegislatorAdmin)

admin.site.unregister(DjangoUser)
admin.site.register(DjangoUser, DjangoUserAdmin)