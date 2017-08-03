# Core Model
import copy
import datetime


# The Epoch (a zero POSIX timestamp).
_EPOCH = datetime.datetime.utcfromtimestamp(0)


class DataStoreErrors():
    BadValueError = Exception
    BadValueError = Exception


datastore_errors = DataStoreErrors


class Property(object):
    _code_name = None
    _name = None
    _indexed = True
    _repeated = False
    _required = False
    _default = None
    _choices = None
    _validator = None
    _verbose_name = None
    _write_empty_list = False

    _attributes = ['_name', '_indexed', '_repeated', '_required', '_default',
                   '_choices', '_validator', '_verbose_name',
                   '_write_empty_list']

    def __init__(self, name=None, indexed=None, repeated=None,
                 required=None, default=None, choices=None, validator=None,
                 verbose_name=None, write_empty_list=None):
        """Constructor.  For arguments see the module docstring."""

        if name is not None:
            if isinstance(name, unicode):
                name = name.encode('utf-8')
            if not isinstance(name, str):
                raise TypeError('Name %r is not a string' % (name,))
            if '.' in name:
                raise ValueError('Name %r cannot contain period characters' % (name,))
            self._name = name

        if indexed is not None:
            self._indexed = indexed
        if repeated is not None:
            self._repeated = repeated
        if required is not None:
            self._required = required
        if default is not None:
            # TODO: Call _validate() on default?
            self._default = default
        if verbose_name is not None:
            self._verbose_name = verbose_name
        if write_empty_list is not None:
            self._write_empty_list = write_empty_list
        if self._repeated and (self._required or self._default is not None):
            raise ValueError('repeated is incompatible with required or default')
        if choices is not None:
            if not isinstance(choices, (list, tuple, set, frozenset)):
                raise TypeError('choices must be a list, tuple or set; received %r' %
                                choices)
            # TODO: Call _validate() on each choice?
            self._choices = frozenset(choices)
        if validator is not None:
            # The validator is called as follows:
            #   value = validator(prop, value)
            # It should return the value to be used, or raise an exception.
            # It should be idempotent, i.e. calling it a second time should
            # not further modify the value.  So a validator that returns e.g.
            # value.lower() or value.strip() is fine, but one that returns
            # value + '$' is not.
            if not hasattr(validator, '__call__'):
                raise TypeError('validator must be callable or None; received %r' %
                                validator)
            self._validator = validator

    def _set_value(self, entity, value):
        """Internal helper to set a value in an entity for a Property.
        This performs validation first.  For a repeated Property the value
        should be a list.
        """
        if self._repeated:
            if not isinstance(value, (list, tuple, set, frozenset)):
                raise datastore_errors.BadValueError('Expected list or tuple, got %r' %
                                                     (value,))
            value = [self._do_validate(v) for v in value]
        else:
            if value is not None:
                value = self._do_validate(value)
        self._store_value(entity, value)

    def _do_validate(self, value):
        # if isinstance(value, _BaseValue):
        #    return value
        value = self._call_shallow_validation(value)
        if self._validator is not None:
            newvalue = self._validator(self, value)
            if newvalue is not None:
                value = newvalue
        if self._choices is not None:
            if value not in self._choices:
                raise datastore_errors.BadValueError(
                    'Value %r for property %s is not an allowed choice' %
                    (value, self._name))
        return value

    def _call_shallow_validation(self, value):
        """Call the initial set of _validate() methods.
        This is similar to _call_to_base_type() except it only calls
        those _validate() methods that can be called without needing to
        call _to_base_type().
        An example: suppose the class hierarchy is A -> B -> C ->
        Property, and suppose A defines _validate() only, but B and C
        define _validate() and _to_base_type().  The full list of
        methods called by _call_to_base_type() is:
          A._validate()
          B._validate()
          B._to_base_type()
          C._validate()
          C._to_base_type()
        This method will call A._validate() and B._validate() but not the
        others.
        """
        methods = []
        for method in self._find_methods('_validate', '_to_base_type'):
            if method.__name__ != '_validate':
                break
            methods.append(method)
        call = self._apply_list(methods)
        return call(value)

    @classmethod
    def _find_methods(cls, *names, **kwds):
        """Compute a list of composable methods.
        Because this is a common operation and the class hierarchy is
        static, the outcome is cached (assuming that for a particular list
        of names the reversed flag is either always on, or always off).
        Args:
          *names: One or more method names.
          reverse: Optional flag, default False; if True, the list is
            reversed.
        Returns:
          A list of callable class method objects.
        """
        reverse = kwds.pop('reverse', False)
        assert not kwds, repr(kwds)
        cache = cls.__dict__.get('_find_methods_cache')
        if cache:
            hit = cache.get(names)
            if hit is not None:
                return hit
        else:
            cls._find_methods_cache = cache = {}
        methods = []
        for c in cls.__mro__:
            for name in names:
                method = c.__dict__.get(name)
                if method is not None:
                    methods.append(method)
        if reverse:
            methods.reverse()
        cache[names] = methods
        return methods

    def _store_value(self, entity, value):
        """Internal helper to store a value in an entity for a Property.
        This assumes validation has already taken place.  For a repeated
        Property the value should be a list.
        """
        entity._values[self._name] = value

    def _apply_list(self, methods):
        """Return a single callable that applies a list of methods to a value.
        If a method returns None, the last value is kept; if it returns
        some other value, that replaces the last value.  Exceptions are
        not caught.
        """
        def call(value):
            for method in methods:
                newvalue = method(self, value)
                if newvalue is not None:
                    value = newvalue
            return value
        return call

    def __get__(self, entity, unused_cls=None):
        """Descriptor protocol: get the value from the entity."""
        if entity is None:
            return self  # __get__ called on class
        return self._get_value(entity)

    def _apply_to_values(self, entity, function):
        """Apply a function to the property value/values of a given entity.
        This retrieves the property value, applies the function, and then
        stores the value back.  For a repeated property, the function is
        applied separately to each of the values in the list.  The
        resulting value or list of values is both stored back in the
        entity and returned from this method.
        """
        value = self._retrieve_value(entity, self._default)
        if self._repeated:
            if value is None:
                value = []
                self._store_value(entity, value)
            else:
                value[:] = map(function, value)
        else:
            if value is not None:
                newvalue = function(value)
                if newvalue is not None and newvalue is not value:
                    self._store_value(entity, newvalue)
                    value = newvalue
        return value

    def _get_value(self, entity):
        """Internal helper to get the value for this Property from an entity.
        For a repeated Property this initializes the value to an empty
        list if it is not set.
        """
        return self._get_user_value(entity)

    def _delete_value(self, entity):
        """Internal helper to delete the value for this Property from an entity.
        Note that if no value exists this is a no-op; deleted values will
        not be serialized but requesting their value will return None (or
        an empty list in the case of a repeated Property).
        """
        if self._name in entity._values:
            del entity._values[self._name]

    def _get_user_value(self, entity):
        """Return the user value for this property of the given entity.
        This implies removing the _BaseValue() wrapper if present, and
        if it is, calling all _from_base_type() methods, in the reverse
        method resolution order of the property's class.  It also handles
        default values and repeated properties.
        """
        return self._apply_to_values(entity, self._opt_call_from_base_type)

    def _opt_call_from_base_type(self, value):
        """Call _from_base_type() if necessary.
        If the value is a _BaseValue instance, unwrap it and call all
        _from_base_type() methods.  Otherwise, return the value
        unchanged.
        """
        # if isinstance(value, _BaseValue):
        #    value = self._call_from_base_type(value.b_val)
        return value

    def _retrieve_value(self, entity, default=None):
        """Internal helper to retrieve the value for this Property from an entity.
        This returns None if no value is set, or the default argument if
        given.  For a repeated Property this returns a list if a value is
        set, otherwise None.  No additional transformations are applied.
        """
        return entity._values.get(self._name, default)

    def _fix_up(self, cls, code_name):
        """Internal helper called to tell the property its name.
        This is called by _fix_up_properties() which is called by
        MetaModel when finishing the construction of a Model subclass.
        The name passed in is the name of the class attribute to which the
        Property is assigned (a.k.a. the code name).  Note that this means
        that each Property instance must be assigned to (at most) one
        class attribute.  E.g. to declare three strings, you must call
        StringProperty() three times, you cannot write
        foo = bar = baz = StringProperty()
        """
        self._code_name = code_name
        if self._name is None:
            self._name = code_name


class TextProperty(Property):
    """An unindexed Property whose value is a text string of unlimited length."""

    def _validate(self, value):
        if isinstance(value, basestring):
            # Decode from UTF-8 -- if this fails, we can't write it.
            try:
                value = value.decode('utf-8')
            except UnicodeError:
                raise datastore_errors.BadValueError('Expected valid UTF-8, got %r' %
                                                     (value,))
        else:
            raise datastore_errors.BadValueError('Expected string, got %r' %
                                                 (value,))

    def _to_base_type(self, value):
        if isinstance(value, unicode):
            return value.encode('utf-8')

    def _from_base_type(self, value):
        if isinstance(value, str):
            try:
                return unicode(value, 'utf-8')
            except UnicodeDecodeError:
                # Since older versions of NDB could write non-UTF-8 TEXT
                # properties, we can't just reject these.  But _validate() now
                # rejects these, so you can't write new non-UTF-8 TEXT
                # properties.
                # TODO: Eventually we should close this hole.
                pass


class StringProperty(TextProperty):
    """An indexed Property whose value is a text string of limited length."""
    _indexed = True


class BooleanProperty(Property):
    """A Property whose value is a Python bool."""
    # TODO: Allow int/long values equal to 0 or 1?

    def _validate(self, value):
        if not isinstance(value, bool):
            raise datastore_errors.BadValueError('Expected bool, got %r' %
                                                 (value,))
        return value

    def _db_set_value(self, v, unused_p, value):
        if not isinstance(value, bool):
            raise TypeError('BooleanProperty %s can only be set to bool values; '
                            'received %r' % (self._name, value))
        v.set_booleanvalue(value)

    def _db_get_value(self, v, unused_p):
        if not v.has_booleanvalue():
            return None
        # The booleanvalue field is an int32, so booleanvalue() returns an
        # int, hence the conversion.
        return bool(v.booleanvalue())


class IntegerProperty(Property):
    """A Property whose value is a Python int or long (or bool)."""

    def _validate(self, value):
        if not isinstance(value, (int, long)):
            raise datastore_errors.BadValueError('Expected integer, got %r' %
                                                 (value,))
        return int(value)

    def _db_set_value(self, v, unused_p, value):
        if not isinstance(value, (bool, int, long)):
            raise TypeError('IntegerProperty %s can only be set to integer values; '
                            'received %r' % (self._name, value))
        v.set_int64value(value)

    def _db_get_value(self, v, unused_p):
        if not v.has_int64value():
            return None
        return int(v.int64value())


class FloatProperty(Property):
    """A Property whose value is a Python float.
    Note: int, long and bool are also allowed.
    """

    def _validate(self, value):
        if not isinstance(value, (int, long, float)):
            raise datastore_errors.BadValueError('Expected float, got %r' %
                                                 (value,))
        return float(value)

    def _db_set_value(self, v, unused_p, value):
        if not isinstance(value, (bool, int, long, float)):
            raise TypeError('FloatProperty %s can only be set to integer or float '
                            'values; received %r' % (self._name, value))
        v.set_doublevalue(float(value))

    def _db_get_value(self, v, unused_p):
        if not v.has_doublevalue():
            return None
        return v.doublevalue()


class _StructuredGetForDictMixin(Property):
    """Mixin class so *StructuredProperty can share _get_for_dict().
    The behavior here is that sub-entities are converted to dictionaries
    by calling to_dict() on them (also doing the right thing for
    repeated properties).
    NOTE: Even though the _validate() method in StructuredProperty and
    LocalStructuredProperty are identical, they cannot be moved into
    this shared base class.  The reason is subtle: _validate() is not a
    regular method, but treated specially by _call_to_base_type() and
    _call_shallow_validation(), and the class where it occurs matters
    if it also defines _to_base_type().
    """

    def _get_for_dict(self, entity):
        value = self._get_value(entity)
        if self._repeated:
            value = [v._to_dict() for v in value]
        elif value is not None:
            value = value._to_dict()
        return value


class StructuredProperty(_StructuredGetForDictMixin):
    """A Property whose value is itself an entity.
    The values of the sub-entity are indexed and can be queried.
    See the module docstring for details.
    """

    _modelclass = None

    _attributes = ['_modelclass'] + Property._attributes

    def __init__(self, modelclass, name=None, **kwds):
        super(StructuredProperty, self).__init__(name=name, **kwds)
        if self._repeated:
            if modelclass._has_repeated:
                raise TypeError('This StructuredProperty cannot use repeated=True '
                                'because its model class (%s) contains repeated '
                                'properties (directly or indirectly).' %
                                modelclass.__name__)
        self._modelclass = modelclass

    def _get_value(self, entity):
        """Override _get_value() to *not* raise UnprojectedPropertyError."""
        value = self._get_user_value(entity)
        if value is None and entity._projection:
            # Invoke super _get_value() to raise the proper exception.
            return super(StructuredProperty, self)._get_value(entity)
        return value

    def __getattr__(self, attrname):
        """Dynamically get a subproperty."""
        # Optimistically try to use the dict key.
        prop = self._modelclass._properties.get(attrname)
        # We're done if we have a hit and _code_name matches.
        if prop is None or prop._code_name != attrname:
            # Otherwise, use linear search looking for a matching _code_name.
            for prop in self._modelclass._properties.values():
                if prop._code_name == attrname:
                    break
            else:
                # This is executed when we never execute the above break.
                prop = None
        if prop is None:
            raise AttributeError('Model subclass %s has no attribute %s' %
                                 (self._modelclass.__name__, attrname))
        prop_copy = copy.copy(prop)
        prop_copy._name = self._name + '.' + prop_copy._name
        # Cache the outcome, so subsequent requests for the same attribute
        # name will get the copied property directly rather than going
        # through the above motions all over again.
        setattr(self, attrname, prop_copy)
        return prop_copy

    def _comparison(self, op, value):
        if op != '=':
            raise datastore_errors.BadFilterError(
                'StructuredProperty filter can only use ==')
        if not self._indexed:
            raise datastore_errors.BadFilterError(
                'Cannot query for unindexed StructuredProperty %s' % self._name)
        # Import late to avoid circular imports.
        from .query import ConjunctionNode, PostFilterNode
        from .query import RepeatedStructuredPropertyPredicate
        if value is None:
            # Import late to avoid circular imports.
            from .query import FilterNode
            return FilterNode(self._name, op, value)
        value = self._do_validate(value)
        value = self._call_to_base_type(value)
        filters = []
        match_keys = []
        # TODO: Why not just iterate over value._values?
        for prop in self._modelclass._properties.itervalues():
            vals = prop._get_base_value_unwrapped_as_list(value)
            if prop._repeated:
                if vals:
                    raise datastore_errors.BadFilterError(
                        'Cannot query for non-empty repeated property %s' % prop._name)
                continue
            assert isinstance(vals, list) and len(vals) == 1, repr(vals)
            val = vals[0]
            if val is not None:
                altprop = getattr(self, prop._code_name)
                filt = altprop._comparison(op, val)
                filters.append(filt)
                match_keys.append(altprop._name)
        if not filters:
            raise datastore_errors.BadFilterError(
                'StructuredProperty filter without any values')
        if len(filters) == 1:
            return filters[0]
        if self._repeated:
            pb = value._to_pb(allow_partial=True)
            pred = RepeatedStructuredPropertyPredicate(match_keys, pb,
                                                       self._name + '.')
            filters.append(PostFilterNode(pred))
        return ConjunctionNode(*filters)

    def _IN(self, value):
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise datastore_errors.BadArgumentError(
                'Expected list, tuple or set, got %r' % (value,))
        from .query import DisjunctionNode, FalseNode
        # Expand to a series of == filters.
        filters = [self._comparison('=', val) for val in value]
        if not filters:
            # DisjunctionNode doesn't like an empty list of filters.
            # Running the query will still fail, but this matches the
            # behavior of IN for regular properties.
            return FalseNode()
        else:
            return DisjunctionNode(*filters)
    IN = _IN

    def _validate(self, value):
        if isinstance(value, dict):
            # A dict is assumed to be the result of a _to_dict() call.
            return self._modelclass(**value)
        if not isinstance(value, self._modelclass):
            raise datastore_errors.BadValueError('Expected %s instance, got %r' %
                                                 (self._modelclass.__name__, value))

    def _has_value(self, entity, rest=None):
        # rest: optional list of attribute names to check in addition.
        # Basically, prop._has_value(self, ent, ['x', 'y']) is similar to
        #   (prop._has_value(ent) and
        #    prop.x._has_value(ent.x) and
        #    prop.x.y._has_value(ent.x.y))
        # assuming prop.x and prop.x.y exist.
        # NOTE: This is not particularly efficient if len(rest) > 1,
        # but that seems a rare case, so for now I don't care.
        ok = super(StructuredProperty, self)._has_value(entity)
        if ok and rest:
            lst = self._get_base_value_unwrapped_as_list(entity)
            if len(lst) != 1:
                raise RuntimeError('Failed to retrieve sub-entity of StructuredProperty'
                                   ' %s' % self._name)
            subent = lst[0]
            if subent is None:
                return True
            subprop = subent._properties.get(rest[0])
            if subprop is None:
                ok = False
            else:
                ok = subprop._has_value(subent, rest[1:])
        return ok

    def _prepare_for_put(self, entity):
        values = self._get_base_value_unwrapped_as_list(entity)
        for value in values:
            if value is not None:
                value._prepare_for_put()

    def _check_property(self, rest=None, require_indexed=True):
        """Override for Property._check_property().
        Raises:
          InvalidPropertyError if no subproperty is specified or if something
          is wrong with the subproperty.
        """
        if not rest:
            raise Exception(
                'Structured property %s requires a subproperty' % self._name)
        self._modelclass._check_properties(
            [rest], require_indexed=require_indexed)

    def _get_base_value_at_index(self, entity, index):
        assert self._repeated
        value = self._retrieve_value(entity, self._default)
        value[index] = self._opt_call_to_base_type(value[index])
        return value[index].b_val

    def _get_value_size(self, entity):
        values = self._retrieve_value(entity, self._default)
        if values is None:
            return 0
        return len(values)


class JsonProperty(TextProperty):
    """A property whose value is any Json-encodable Python object."""

    _json_type = None

    def __init__(self, name=None, compressed=False, json_type=None, **kwds):
        super(JsonProperty, self).__init__(name=name, **kwds)
        self._json_type = json_type

    def _validate(self, value):
        if self._json_type is not None and not isinstance(value, self._json_type):
            raise TypeError('JSON property must be a %s' % self._json_type)

    # Use late import so the dependency is optional.

    def _to_base_type(self, value):
        try:
            import json
        except ImportError:
            import simplejson as json
        return json.dumps(value)

    def _from_base_type(self, value):
        try:
            import json
        except ImportError:
            import simplejson as json
        return json.loads(value)


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
        # p.set_meaning(entity_pb.Property.GD_WHEN)

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


class Model(object):
    id = None
    _has_repeated = False

    @classmethod
    def _get_kind(cls):
        """Return the kind name for this class.
        This defaults to cls.__name__; users may overrid this to give a
        class a different on-disk name than its class name.
        """
        return cls.__name__

    def get_kind(self):
        return self.__class__.__name__

    def __init__(*args, **kwds):
        """Creates a new instance of this model (a.k.a. an entity).
        The new entity must be written to the datastore using an explicit
        call to .put().
        Keyword Args:
          key: Key instance for this model. If key is used, id and parent must
            be None.
          id: Key id for this model. If id is used, key must be None.
          parent: Key instance for the parent model or None for a top-level one.
            If parent is used, key must be None.
          namespace: Optional namespace.
          app: Optional app ID.
          **kwds: Keyword arguments mapping to properties of this model.
        Note: you cannot define a property named key; the .key attribute
        always refers to the entity's key.  But you can define properties
        named id or parent.  Values for the latter cannot be passed
        through the constructor, but can be assigned to entity attributes
        after the entity has been created.
        """
        if len(args) > 1:
            raise TypeError('Model constructor takes no positional arguments.')
        # self is passed implicitly through args so users can define a property
        # named 'self'.
        (self,) = args

        self._fix_up_properties()

        get_arg = self.__get_arg
        self.id = get_arg(kwds, 'id')
        self._values = {}
        self._set_attributes(kwds)
        self._fix_up_properties()
        # Set the projection last, otherwise it will prevent _set_attributes().

    @classmethod
    def __get_arg(cls, kwds, kwd):
        """Internal helper method to parse keywords that may be property names."""
        alt_kwd = '_' + kwd
        if alt_kwd in kwds:
            return kwds.pop(alt_kwd)
        if kwd in kwds:
            obj = getattr(cls, kwd, None)
            if not isinstance(obj, Property):
                return kwds.pop(kwd)
        return None

    def _populate(self, **kwds):
        """Populate an instance from keyword arguments.
        Each keyword argument will be used to set a corresponding
        property.  Keywords must refer to valid property name.  This is
        similar to passing keyword arguments to the Model constructor,
        except that no provisions for key, id or parent are made.
        """
        self._set_attributes(kwds)
    populate = _populate

    def _set_attributes(self, kwds):
        """Internal helper to set attributes from keyword arguments.
        Expando overrides this.
        """
        cls = self.__class__
        for name, value in kwds.iteritems():
            prop = getattr(cls, name)  # Raises AttributeError for unknown properties.

            if not isinstance(prop, Property):
                raise TypeError('Cannot set non-property %s' % name)
            prop._set_value(self, value)

    @classmethod
    def _fix_up_properties(cls):
        """Fix up the properties by calling their _fix_up() method.
        Note: This is called by MetaModel, but may also be called manually
        after dynamically updating a model class.
        """
        # Verify that _get_kind() returns an 8-bit string.
        kind = cls._get_kind()
        if not isinstance(kind, basestring):
            raise Exception('Class %s defines a _get_kind() method that returns '
                            'a non-string (%r)' % (cls.__name__, kind))

        if not isinstance(kind, str):
            try:
                kind = kind.encode('ascii')  # ASCII contents is okay.
            except UnicodeEncodeError:
                raise Exception('Class %s defines a _get_kind() method that returns '
                                'a Unicode string (%r); please encode using utf-8' %
                                (cls.__name__, kind))

        cls._properties = {}  # Map of {name: Property}
        if cls.__module__ == __name__:  # Skip the classes in *this* file.
            return

        for name in set(dir(cls)):
            attr = getattr(cls, name, None)

            # if isinstance(attr, ModelAttribute) and not isinstance(attr, ModelKey):
            if isinstance(attr, Property):
                if name.startswith('_'):
                    raise TypeError('ModelAttribute %s cannot begin with an underscore '
                                    'character. _ prefixed attributes are reserved for '
                                    'temporary Model instance values.' % name)

                attr._fix_up(cls, name)

                if isinstance(attr, Property):
                    if (attr._repeated or
                       (isinstance(attr, StructuredProperty) and attr._modelclass._has_repeated)):
                        cls._has_repeated = True
                    cls._properties[attr._name] = attr
