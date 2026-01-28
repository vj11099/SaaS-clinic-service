from django.db import connection


def make_key(key, key_prefix, version):
    return f"{connection.schema_name}:{key}"


def reverse_key(key):
    return key.split(":", 1)[1]
