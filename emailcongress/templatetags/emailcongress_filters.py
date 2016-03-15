from django import template

register = template.Library()


@register.filter
def is_in(var, obj):
    return var in obj


@register.filter
def humanize_list(value):
    """
    Represents a list in a humanized way with commas and ending with ", and ..."

    @param value: list of values
    @type value: list
    @return: humanized string representation of list
    @rtype: string
    """
    if len(value) == 0:
        return ""
    elif len(value) == 1:
        return value[0]

    s = ", ".join(value[:-1])

    if len(value) > 3:
        s += ","

    return "%s and %s" % (s, value[-1])


@register.filter
def humanize_legislator_list(legislators):
    """
    Represents a list in a humanized way with commas and ending with ", and ..."

    @param legislators: list or QuerySet of legislators
    @type legislators: list|django.db.models.query.QuerySet
    @return: humanized string representation of list
    @rtype: string
    """
    return humanize_list([leg.full_title_and_full_name for leg in legislators])


@register.filter
def call(obj, method_name):
    method = getattr(obj, method_name)
    if '__callArg' in obj.__dict__:
        ret = method(*obj.__callArg)
        del obj.__callArg
        return ret
    return method()


@register.filter
def args(obj, arg):
    if '__callArg' not in obj.__dict__:
        obj.__callArg = []
    obj.__callArg += [arg]
    return obj


@register.tag
def remove_whitespace(parser, token):
    nodelist = parser.parse(('endremove_whitespace',))
    parser.delete_first_token()
    return RemoveSpaces(nodelist)


@register.tag
def set_var(parser, token):
    """
    {% set <var_name>  = <var_value> %}
    """
    parts = token.split_contents()
    if len(parts) < 4:
        raise template.TemplateSyntaxError("'set' tag must be of the form:  {% set <var_name>  = <var_value> %}")
    return SetVarNode(parts[1], parts[3])


class RemoveSpaces(template.Node):

    def __init__(self, nodelist):
        self.nodelist = nodelist

    def render(self, context):
        output = self.nodelist.render(context)
        return ''.join(output.split()) # modify behavior if desired


class SetVarNode(template.Node):

    def __init__(self, var_name, var_value):
        self.var_name = var_name
        self.var_value = var_value

    def render(self, context):
        try:
            value = template.Variable(self.var_value).resolve(context)
        except template.VariableDoesNotExist:
            value = ""
        context[self.var_name] = value
        return u""
