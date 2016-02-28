from django import template

register = template.Library()


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
