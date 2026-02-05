from .views.roles_and_permissions import (
    PermissionViewSet,
    RoleViewSet,
    UserRoleViewSet
)
from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import LoginView, RegisterUserView, VerifyUserView
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'permissions', PermissionViewSet, basename='permission')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'user-roles', UserRoleViewSet, basename='user-role')

urlpatterns = [
    path('register/', RegisterUserView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('verify/', VerifyUserView.as_view(), name='verify_password'),
    path('', include(router.urls)),
]

"""
This creates the following endpoints:

PERMISSIONS:
============
GET     /api/permissions/                          - List all permissions
POST    /api/permissions/                          - Create a new permission
GET     /api/permissions/{id}/                     - Get specific permission
PUT     /api/permissions/{id}/                     - Update permission (full)
PATCH   /api/permissions/{id}/                     - Update permission (partial)
DELETE  /api/permissions/{id}/                     - Soft delete permission
POST    /api/permissions/{id}/restore/             - Restore deleted permission

Query Parameters for GET /api/permissions/:
- ?is_active=true/false                            - Filter by active status
- ?search=<term>                                   - Search in name or description


ROLES:
======
GET     /api/roles/                                - List all roles
POST    /api/roles/                                - Create a new role
GET     /api/roles/{id}/                           - Get specific role with permissions
PUT     /api/roles/{id}/                           - Update role (full)
PATCH   /api/roles/{id}/                           - Update role (partial)
DELETE  /api/roles/{id}/                           - Soft delete role
POST    /api/roles/{id}/restore/                   - Restore deleted role

Query Parameters for GET /api/roles/:
- ?is_active=true/false                            - Filter by active status
- ?search=<term>                                   - Search in name or description
- ?include_system=true/false                       - Include/exclude system roles


ROLE-PERMISSION ASSIGNMENT:
===========================
POST    /api/roles/assign-permissions/             - Assign permissions to role
        Body: {"role_id": 1, "permission_ids": [1, 2, 3]}

POST    /api/roles/remove-permissions/             - Remove permissions from role
        Body: {"role_id": 1, "permission_ids": [1, 2, 3]}


USER-ROLE ASSIGNMENT:
=====================
POST    /api/user-roles/assign-roles/              - Assign roles to user
        Body: {"user_id": 1, "role_ids": [1, 2, 3]}

POST    /api/user-roles/remove-roles/              - Remove roles from user
        Body: {"user_id": 1, "role_ids": [1, 2, 3]}

GET     /api/user-roles/user/{user_id}/            - Get user with roles & permissions

GET     /api/user-roles/role/{role_id}/users/      - Get all users with specific role


EXAMPLE USAGE:
==============

1. Create a permission:
POST /api/permissions/
{
    "name": "users.create",
    "description": "Can create users"
}

2. Create a role:
POST /api/roles/
{
    "name": "Admin",
    "description": "Administrator role"
}

3. Assign permissions to role:
POST /api/roles/assign-permissions/
{
    "role_id": 1,
    "permission_ids": [1, 2, 3, 4]
}

4. Assign roles to user:
POST /api/user-roles/assign-roles/
{
    "user_id": 5,
    "role_ids": [1, 2]
}

5. Get user's roles and permissions:
GET /api/user-roles/user/5/

6. Remove permission from role:
POST /api/roles/remove-permissions/
{
    "role_id": 1,
    "permission_ids": [3]
}

7. Remove role from user:
POST /api/user-roles/remove-roles/
{
    "user_id": 5,
    "role_ids": [2]
}
"""
