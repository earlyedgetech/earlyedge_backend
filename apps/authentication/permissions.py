from admin_security.models import AdminMember
from rest_framework.permissions import BasePermission
from students.models import Student


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, Student) and request.user.is_authenticated


class IsAdminMember(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, AdminMember) and request.user.is_authenticated


class HasDashboardPermission(BasePermission):
    """RBAC gate for a specific permission codename.

    Usage: permission_classes = [IsAdminMember, HasDashboardPermission('manage_members')]
    """

    def __init__(self, codename):
        self.codename = codename

    def __call__(self):
        return self

    def has_permission(self, request, view):
        user = request.user
        return (
            isinstance(user, AdminMember)
            and user.is_authenticated
            and user.has_permission(self.codename)
        )
