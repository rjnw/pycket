
from pycket import values

class W_CType(values.W_Object):

    errorname = "ctype"
    _attrs_ = []

    def __init__(self):
        raise NotImplementedError("abstract base class")

    def basetype(self):
        raise NotImplementedError("abstract base class")

    def scheme_to_c(self):
        raise NotImplementedError("abstract base class")

    def c_to_scheme(self):
        raise NotImplementedError("abstract base class")

    def sizeof(self):
        raise NotImplementedError("abstract base class")

class W_PrimitiveCType(W_CType):

    _immutable_fields_ = ["name", "size", "alignment"]

    def __init__(self, name, size, alignment):
        assert isinstance(name, values.W_Symbol)
        self.name      = name
        self.size      = size
        self.alignment = alignment

    def sizeof(self):
        return self.size

    def alignof(self):
        return self.alignment

    def basetype(self):
        return self.name

    c_to_scheme = scheme_to_c = lambda self: values.w_false

    def tostring(self):
        return self.name.utf8value

class W_DerivedCType(W_CType):

    _immutable_fields_ = ["ctype", "racket_to_c", "c_to_racket"]

    def __init__(self, ctype, racket_to_c, c_to_racket):
        assert isinstance(ctype, W_CType)
        self.ctype       = ctype
        self.racket_to_c = racket_to_c
        self.c_to_racket = c_to_racket

    def sizeof(self):
        return self.ctype.sizeof()

    def alignof(self):
        return self.ctype.alignof()

    def has_conversions(self):
        return (self.racket_to_c is not values.w_false or
                self.c_to_racket is not values.w_false)

    def basetype(self):
        if self.has_conversions():
            return self.ctype
        return self.ctype.basetype()

    def scheme_to_c(self):
        return self.racket_to_c

    def c_to_scheme(self):
        return self.c_to_racket

    def tostring(self):
        if self.racket_to_c is values.w_false and self.c_to_racket is values.w_false:
            return "<ctype:%s" % self.ctype.tostring()
        return "#<ctype>"

