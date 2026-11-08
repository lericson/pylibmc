"""Constants and functionality related to them"""

import warnings

import _pylibmc

#: Mapping of exception name => class
errors = tuple(e for (n, e) in _pylibmc.exceptions)
# *Cough* Uhm, not the prettiest of things but this unpacks all exception
# objects and sets them on the package module object currently constructed.
import sys
modpkg = sys.modules[__name__.split(".", 1)[0]]
modself = sys.modules[__name__]
for name, exc in _pylibmc.exceptions:
    setattr(modself, name, exc)
    setattr(modpkg, name, exc)

all_behaviors = _pylibmc.all_behaviors
all_callbacks = _pylibmc.all_callbacks
hashers, hashers_rvs = {}, {}
distributions, distributions_rvs = {}, {}
# Not the prettiest way of doing things, but works well.
for name in dir(_pylibmc):
    if name.startswith("hash_"):
        key, value = name[5:], getattr(_pylibmc, name)
        hashers[key] = value
        hashers_rvs[value] = key
    elif name.startswith("distribution_"):
        key, value = name[13:].replace("_", " "), getattr(_pylibmc, name)
        distributions[key] = value
        distributions_rvs[value] = key

def warn_verify_keys(stacklevel):
    """Warn that the *verify_keys* behavior does nothing.

    *stacklevel* counts from the function that calls this one (1 is that
    function, 2 its caller, and so on), as for :func:`warnings.warn`.
    """
    warnings.warn("pylibmc always verifies keys, so the verify_keys behavior "
                  "is ignored and no longer needed; remove it",
                  DeprecationWarning, stacklevel=stacklevel + 1)

class BehaviorDict(dict):
    def __init__(self, client, *args, **kwds):
        super().__init__(*args, **kwds)
        self.client = client

    def __setitem__(self, name, value):
        if name == "verify_keys":
            warn_verify_keys(2)
            return
        super().__setitem__(name, value)
        self.client.set_behaviors({name: value})

    def update(self, d):
        d = dict(d)
        if "verify_keys" in d:
            warn_verify_keys(2)
            del d["verify_keys"]
        super().update(d)
        self.client.set_behaviors(d.copy())
