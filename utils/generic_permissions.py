# permissions.py
# from rest_framework import permissions
# from django.db import connection
#
#
# class IsPublicSchemaOnly(permissions.BasePermission):
#    """Only allow access from public schema"""
#    message = "This endpoint is only accessible from the main domain."
#
#    def has_permission(self, request, view):
#        return connection.schema_name == 'public'
#
#
# class IsTenantSchemaOnly(permissions.BasePermission):
#    """Only allow access from tenant schemas"""
#    message = "This endpoint is only accessible from organization domains."
#
#    def has_permission(self, request, view):
#        return connection.schema_name != 'public'
