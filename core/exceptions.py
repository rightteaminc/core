# Common Exceptions


class PermissionException(Exception):
    """
    Internal Exception when permission to an object cannot be granted
    Any handler catching this error should return a 403 response code
    """


class AuthenticationException(Exception):
    """
    Internal Exception when an authentication attempt fails
    Any handler catching this error should return a 401 response code
    """


class DoesNotExistException(Exception):
    """
    Internal exception when an object cannot be found
    Any handler catching this error should return a 404 response code
    """


class ConflictException(Exception):
    """
    Internal Exception when an object could not be created due to conflict, such as when the object
    already exists.
    Any handler catching this error should return a 409 response code
    """
