def bool_eval(v):
    if type(v) is bool:
        return v
    elif type(v) is int:
        return v != 0
    else:
        return v.lower() in ("yes", "true", "t", "1")


def ordinal(n):
    if type(n) == str: n = int(n)
    return "%d%s" % (n, "tsnrhtdd"[(n / 10 % 10 != 1) * (n % 10 < 4) * n % 10::4])


def construct_link(protocol, hostname, path, get_param_dict=None):
    return protocol + '://' + hostname + path