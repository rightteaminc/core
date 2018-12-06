# Datastore utilities

import base64
from google.appengine.ext import ndb

SEPARATOR = chr(30)
INTPREFIX = chr(31)
# Error Templates
_keystr_type_err = 'Keystrings must of type basestring. Received: %s'
_id_type_err = 'Resource Ids must be an instance of basestring. Received: %s'
_kind_err = 'Expected keystr for kind %s but found kind %s instead.'

def get_resource_id_from_key(key):
    """
    Convert a ndb.Key() into a portable `str` resource id
    :param key: An instance of `ndb.Key`
    """

    pair_strings = []

    pairs = key.pairs()

    for pair in pairs:
        kind = unicode(pair[0])
        key_or_id = pair[1]

        if isinstance(key_or_id, (int, long)):
            key_or_id = unicode(INTPREFIX + unicode(key_or_id))

        pair_strings.append(kind + SEPARATOR + key_or_id)

    buff = SEPARATOR.join(pair_strings)
    encoded = base64.urlsafe_b64encode(buff)
    encoded = encoded.replace('=', '')
    return encoded


def get_key_from_resource_id(resource_id):
    """
    Convert a portable `str` resource id into a ndb.Key
    :param resource_id: A `str` resource_id
    """

    # Add padding back on as needed...
    modulo = len(resource_id) % 4
    if modulo != 0:
        resource_id += ('=' * (4 - modulo))

    # decode the url safe resource id
    decoded = base64.urlsafe_b64decode(str(resource_id))

    key_pairs = []
    bits = decoded.split(SEPARATOR)

    for bit in bits:
        if (bit[0] == INTPREFIX):
            bit = int(bit[1:])
        key_pairs.append(bit)

    return ndb.Key(*key_pairs)


def get_entity_key_by_keystr(expected_kind, keystr):
    """
    Helper to get a key for an ndb entity by its urlsafe keystr
    Args:
        expected_kind: The expected kind of ndb.Key as case-sensative string
        keystr: ndb.Key string representation
    Returns:
        An instance of Entity with key of keystr
    Raises:
        ValueError: The keystr is None or of wrong type
        ValueError: The expected_kind does not match the kind of keystr
    """

    if not keystr or not isinstance(keystr, basestring):
        raise ValueError(_keystr_type_err % keystr)

    # Resolve the ndb key
    ndb_key = ndb.Key(urlsafe=keystr)

    # Validate the kind
    if not ndb_key.kind() == expected_kind:
        raise ValueError(_kind_err % (expected_kind, ndb_key.kind()))

    return ndb_key


def get_entity_by_resource_id(expected_kind, resource_id):
    """
    Get an entity by its resource_id
    Args:
        expected_kind: The expected kind of ndb.Key as case-sensative string
        resource_id: Portable string id that resolves to an ndb.Key
    Returns:
        An instance of Entity corresponding to resource_id
    Raises:
        ValueError: The keystr is None or of wrong type
        ValueError: The expected_kind does not match the kind of keystr
        InvalidIdException: resource_id could not be converted to ndb.Key
    """

    if not resource_id or not isinstance(resource_id, basestring):
        raise ValueError(_id_type_err % resource_id)

    try:
        # Resolve the ndb key - Note: This will throw if invalid
        ndb_key = get_key_from_resource_id(resource_id)

        # Validate the kind
        if not ndb_key.kind() == expected_kind:
            raise ValueError(_kind_err % (expected_kind, ndb_key.kind()))

        return ndb_key.get()  # Could return None
    except (ValueError, AttributeError, IndexError, TypeError):
        raise InvalidIdException("'%s' is not a valid resource id." %
                                 resource_id)



class EntityExists(RuntimeError):
    """Exception to throw for duplicate"""
    pass


class InvalidIdException(ValueError):
    pass


class DoesNotExistException(RuntimeError):
    pass
