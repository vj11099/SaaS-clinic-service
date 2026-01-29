from django.db import connection


def make_key(key):
    return f"{connection.schema_name}:{key}"


def reverse_key(key):
    return key.split(":", 1)[1]
