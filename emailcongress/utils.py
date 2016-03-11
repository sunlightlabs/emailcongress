from urllib import parse


def bool_eval(v):
    if type(v) is bool:
        return v
    elif type(v) is int:
        return v != 0
    elif type(v) is str:
        return v.lower() in ("yes", "true", "t", "1")
    else:
        return v


def ordinal(n):
    if type(n) == str: n = int(n)
    return "%d%s" % (n, "tsnrhtdd"[(n / 10 % 10 != 1) * (n % 10 < 4) * n % 10::4])


def construct_link(protocol, hostname, path, get_param_dict=None):
    link = protocol + '://' + hostname + path
    if get_param_dict is not None:
        link += '?' + parse.urlencode(get_param_dict)
    return link
