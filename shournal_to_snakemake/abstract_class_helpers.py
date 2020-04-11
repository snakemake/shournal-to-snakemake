

class SimpleEquality(object):
    """
    Helper class for the simple comparison of two objects of the same class.
    If their __dict__'s are equal, true is returned
    """
    def __eq__(self, other):
        if isinstance(self, other.__class__):
            return self.__dict__ == other.__dict__
        return NotImplemented