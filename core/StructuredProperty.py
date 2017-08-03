class DateTimeProperty(Property):
    """A Property whose value is a datetime object.
    Note: Unlike Django, auto_now_add can be overridden by setting the
    value before writing the entity.  And unlike classic db, auto_now
    does not supply a default value.  Also unlike classic db, when the
    entity is written, the property values are updated to match what
    was written.  Finally, beware that this also updates the value in
    the in-process cache, *and* that auto_now_add may interact weirdly
    with transaction retries (a retry of a property with auto_now_add
    set will reuse the value that was set on the first try).
    """

    _attributes = Property._attributes + ['_auto_now', '_auto_now_add']

    _auto_now = False
    _auto_now_add = False

    @utils.positional(1 + Property._positional)
    def __init__(self, name=None, auto_now=False, auto_now_add=False, **kwds):
        super(DateTimeProperty, self).__init__(name=name, **kwds)
        # TODO: Disallow combining auto_now* and default?
        if self._repeated:
            if auto_now:
                raise ValueError('DateTimeProperty %s could use auto_now and be '
                                 'repeated, but there would be no point.' % self._name)
            elif auto_now_add:
                raise ValueError('DateTimeProperty %s could use auto_now_add and be '
                                 'repeated, but there would be no point.' % self._name)
        self._auto_now = auto_now
        self._auto_now_add = auto_now_add

    def _validate(self, value):
        if not isinstance(value, datetime.datetime):
            raise datastore_errors.BadValueError('Expected datetime, got %r' %
                                                 (value,))

    def _now(self):
        return datetime.datetime.utcnow()

    def _prepare_for_put(self, entity):
        if (self._auto_now or
                (self._auto_now_add and not self._has_value(entity))):
            value = self._now()
            self._store_value(entity, value)

    def _db_set_value(self, v, p, value):
        if not isinstance(value, datetime.datetime):
            raise TypeError('DatetimeProperty %s can only be set to datetime values; '
                            'received %r' % (self._name, value))
        if value.tzinfo is not None:
            raise NotImplementedError('DatetimeProperty %s can only support UTC. '
                                      'Please derive a new Property to support '
                                      'alternative timezones.' % self._name)
        dt = value - _EPOCH
        ival = dt.microseconds + 1000000 * (dt.seconds + 24 * 3600 * dt.days)
        v.set_int64value(ival)
        p.set_meaning(entity_pb.Property.GD_WHEN)

    def _db_get_value(self, v, unused_p):
        if not v.has_int64value():
            return None
        ival = v.int64value()
        return _EPOCH + datetime.timedelta(microseconds=ival)


def _date_to_datetime(value):
    """Convert a date to a datetime for datastore storage.
    Args:
      value: A datetime.date object.
    Returns:
      A datetime object with time set to 0:00.
    """
    if not isinstance(value, datetime.date):
        raise TypeError('Cannot convert to datetime expected date value; '
                        'received %s' % value)
    return datetime.datetime(value.year, value.month, value.day)


def _time_to_datetime(value):
    """Convert a time to a datetime for datastore storage.
    Args:
      value: A datetime.time object.
    Returns:
      A datetime object with date set to 1970-01-01.
    """
    if not isinstance(value, datetime.time):
        raise TypeError('Cannot convert to datetime expected time value; '
                        'received %s' % value)
    return datetime.datetime(1970, 1, 1,
                             value.hour, value.minute, value.second,
                             value.microsecond)


class DateProperty(DateTimeProperty):
    """A Property whose value is a date object."""

    def _validate(self, value):
        if not isinstance(value, datetime.date):
            raise datastore_errors.BadValueError('Expected date, got %r' %
                                                 (value,))

    def _to_base_type(self, value):
        assert isinstance(value, datetime.date), repr(value)
        return _date_to_datetime(value)

    def _from_base_type(self, value):
        assert isinstance(value, datetime.datetime), repr(value)
        return value.date()

    def _now(self):
        return datetime.datetime.utcnow().date()


class TimeProperty(DateTimeProperty):
    """A Property whose value is a time object."""

    def _validate(self, value):
        if not isinstance(value, datetime.time):
            raise datastore_errors.BadValueError('Expected time, got %r' %
                                                 (value,))

    def _to_base_type(self, value):
        assert isinstance(value, datetime.time), repr(value)
        return _time_to_datetime(value)

    def _from_base_type(self, value):
        assert isinstance(value, datetime.datetime), repr(value)
        return value.time()

    def _now(self):
        return datetime.datetime.utcnow().time()
