
from rpython.rlib             import jit, unroll, rweakref
from rpython.rlib.objectmodel import specialize

def make_map_type(getter, keyclass):

    class Map(object):
        """ A basic implementation of a map which assigns Racket values to an index
        based on the identity of the Racket value. A Map consists of

        * indexes: a map from objects to indicies for object described by the current map
        * other_maps: sub maps which are extensions the current map
        """

        _immutable_fields_ = ['indexes', 'other_maps']
        _attrs_ = ['indexes', 'other_maps']

        def __init__(self):
            self.indexes    = {}
            self.other_maps = rweakref.RWeakValueDictionary(keyclass, Map)

        def __iter__(self):
            return self.indexes.iteritems()

        def iterkeys(self):
            return self.indexes.iterkeys()

        def itervalues(self):
            return self.indexes.itervalues()

        def iteritems(self):
            return self.indexes.iteritems()

        @jit.elidable_promote('all')
        def get_index(self, name):
            return self.indexes.get(name, -1)

        @specialize.argtype(2)
        def lookup(self, name, storage, default=None, offset=0):
            idx = self.get_index(name)
            if idx == -1:
                return default
            assert storage is not None
            return getattr(storage, getter)(idx+offset)

        @jit.elidable_promote('all')
        def add_attribute(self, name):
            newmap = self.other_maps.get(name)
            if newmap is None:
                newmap = Map()
                newmap.indexes.update(self.indexes)
                newmap.indexes[name] = len(self.indexes)
                self.other_maps.set(name, newmap)
            return newmap

        def set_storage(self, name, val, storage):
            idx = self.get_index(name)
            self.storage[idx] = val

        @jit.elidable
        def has_attribute(self, name):
            return name in self.indexes

        @jit.elidable
        def storage_size(self):
            return len(self.indexes)

    Map.EMPTY = Map()

    return Map

# TODO Find a beter name for this
def make_caching_map_type(getter, keyclass):

    class Pair(object):
        _attrs_ = ['x', 'y']
        def __init__(self, x, y):
            self.x = x
            self.y = y

        def __eq__(self, other):
            assert isinstance(other, Pair)
            return self.x == other.x and self.y == other.y

        def __hash__(self):
            return hash((self.x, self.y))

    class CachingMap(object):
        """ A map implementation which partitions its data into two groups, a collection
        of static data stored in the map itself, and a collection of indexes used to
        index into a corresponding data array.

        This partitioning allows structures such as impersonators to share not just
        their layout but common data as well.
        """
        _immutable_fields_ = ['indexes', 'static_data', 'static_submaps', 'dynamic_submaps']
        _attrs_ = ['indexes', 'static_data', 'static_submaps', 'dynamic_submaps']

        def __init__(self):
            self.indexes = {}
            self.static_data = {}
            self.dynamic_submaps = rweakref.RWeakValueDictionary(keyclass, CachingMap)
            self.static_submaps  = rweakref.RWeakValueDictionary(Pair, CachingMap)

        def iterkeys(self):
            for key in self.indexes.iterkeys():
                yield key
            for key in self.static_data.iterkeys():
                yield key

        def iteritems(self):
            for item in self.indexes.iteritems():
                yield item
            for item in self.static_data.iteritems():
                yield item

        def itervalues(self):
            for val in self.indexes.itervalues():
                yield val
            for val in self.static_data.itervalues():
                yield val

        @jit.elidable
        def storage_size(self):
            return len(self.indexes)

        @jit.elidable_promote('all')
        def get_dynamic_index(self, name):
            return self.indexes.get(name, -1)

        @jit.elidable_promote('all')
        def get_static_data(self, name, default):
            if name not in self.static_data:
                return default
            return self.static_data[name]

        @specialize.argtype(2)
        def lookup(self, name, storage, default=None, offset=0):
            idx = self.get_dynamic_index(name)
            if idx == -1:
                return self.get_static_data(name, default)
            assert storage is not None
            return getattr(storage, getter)(idx+offset)

        @jit.elidable_promote('all')
        def add_static_attribute(self, name, value):
            assert name not in self.indexes and name not in self.static_data
            key = Pair(name, value)
            newmap = self.static_submaps.get(key)
            if newmap is None:
                newmap = CachingMap()
                newmap.indexes.update(self.indexes)
                newmap.static_data.update(self.static_data)
                newmap.static_data[name] = value
                self.static_submaps.set(key, newmap)
            return newmap

        @jit.elidable_promote('all')
        def add_dynamic_attribute(self, name):
            assert name not in self.indexes and name not in self.static_data
            newmap = self.dynamic_submaps.get(name)
            if newmap is None:
                newmap = CachingMap()
                newmap.indexes.update(self.indexes)
                newmap.static_data.update(self.static_data)
                newmap.indexes[name] = len(self.indexes)
                self.dynamic_submaps.set(name, newmap)
            return newmap

        @jit.elidable
        def is_dynamic_attribute(self, name):
            return name in seld.indexes

        @jit.elidable
        def is_static_attribute(self, name):
            return name in self.static_data

        def is_leaf(self):
            return not self.indexes and not self.static_data

        @jit.elidable_promote('all')
        def has_key(self, key):
            return key in self.indexes or key in self.static_data

        @jit.elidable_promote('all')
        def has_same_shape(self, other):
            if self is other:
                return True
            for key in self.iterkeys():
                if not other.has_key(key):
                    return False
            for key in other.iterkeys():
                if not self.has_key(key):
                    return False
            return True

    CachingMap.EMPTY = CachingMap()
    return CachingMap

# These maps are simply unique products of various other map types.
# They are unique based on their component maps.
def make_composite_map_type(keyclass, shared_storage=False):

    class Pair(object):
        _attrs_ = ['x', 'y']
        def __init__(self, x, y):
            self.x = x
            self.y = y

        def __eq__(self, other):
            assert isinstance(other, Pair)
            return self.x == other.x and self.y == other.y

        def __hash__(self):
            return hash((self.x, self.y))

    class CompositeMap(object):
        _immutable_fields_ = ['handlers', 'properties']

        @staticmethod
        @jit.elidable
        def instantiate(handlers, properties):
            key = Pair(handlers, properties)
            result = CompositeMap.CACHE.get(key)
            if result is None:
                result = CompositeMap(handlers, properties)
                CompositeMap.CACHE.set(key, result)
            return result

        def __init__(self, handlers, properties):
            self.handlers = handlers
            self.properties = properties

        @specialize.argtype(2)
        def lookup_handler(self, key, storage, default=None):
            jit.promote(self)
            return self.handlers.lookup(key, storage, default=default)

        @specialize.argtype(2)
        def lookup_property(self, key, storage, default=None):
            """ We make the assumption that data for the handlers are laid out
            in the form [handler_0, handler_1, ..., property_0, property_1, ...]"""
            jit.promote(self)
            offset = self.handlers.storage_size() if shared_storage else 0
            return self.properties.lookup(key, storage, default=default, offset=offset)

    CompositeMap.CACHE = rweakref.RWeakValueDictionary(Pair, CompositeMap)
    return CompositeMap

