from rest_framework.permissions import BasePermission


class IsRatingOwner(BasePermission):
    """ Custom permission for Rating """

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        if request.method == 'POST':
            # Only an authenticated user can create a rating
            return request.user and request.user.is_authenticated

        # For other methods they're object level handled in has_object_permission
        return True

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True

        if request.method in ('PUT', 'PATCH'):
            # Admins can't edit users ratings to avoid disputes and rating manipulation
            # Write permissions are only allowed to the owner of the rating
            return obj.user == request.user

        # Delete permissions are only allowed to the owner or admins
        return obj.user == request.user or request.user.is_staff


class DenyUpdate(BasePermission):
    """ Custom permission to deny updates """

    def has_permission(self, request, view):
        if request.method in ('PUT', 'PATCH'):
            return False
        return True


class IsHistoryOwner(BasePermission):
    """ Custom permission for WatchHistory """

    def has_object_permission(self, request, view, obj):
        # Only the owner of the watch history can access or delete it
        return obj.user == request.user
