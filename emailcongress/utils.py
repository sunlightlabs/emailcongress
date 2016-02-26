def bool_eval(v):
    if type(v) is bool:
        return v
    else:
        return v.lower() in ("yes", "true", "t", "1")


def ordinal(n):
    if type(n) == str: n = int(n)
    return "%d%s" % (n, "tsnrhtdd"[(n / 10 % 10 != 1) * (n % 10 < 4) * n % 10::4])
