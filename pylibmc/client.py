"""Python-level wrapper client"""

import _pylibmc
from .consts import (hashers, distributions,
                     hashers_rvs, distributions_rvs,
                     BehaviorDict)

class Client(_pylibmc.client):
    def __init__(self, servers, binary=False, username=None, password=None):
        """Initialize a memcached client instance.

        This connects to the servers in *servers*, which will default to being
        TCP servers. If it looks like a filesystem path, a UNIX socket. If
        prefixed with `udp:`, a UDP connection.

        If *binary* is True, the binary memcached protocol is used.

        SASL authentication is supported if libmemcached supports it (check
        *pylibmc.support_sasl*). Requires both username and password.
        Note that SASL requires *binary*=True.
        """
        self.binary = binary
        self.addresses = list(servers)
        addr_tups = []
        for server in servers:
            addr = server
            port = 11211
            if server.startswith("udp:"):
                stype = _pylibmc.server_type_udp
                addr = addr[4:]
                if ":" in server:
                    (addr, port) = addr.split(":", 1)
                    port = int(port)
            elif ":" in server:
                stype = _pylibmc.server_type_tcp
                (addr, port) = server.split(":", 1)
                port = int(port)
            elif "/" in server:
                stype = _pylibmc.server_type_unix
                port = 0
            else:
                stype = _pylibmc.server_type_tcp
            addr_tups.append((stype, addr, port))
        super(Client, self).__init__(servers=addr_tups, binary=binary, username=username, password=password)

    def __repr__(self):
        return "%s(%r, binary=%r)" % (self.__class__.__name__,
                                      self.addresses, self.binary)

    def __str__(self):
        addrs = ", ".join(map(str, self.addresses))
        return "<%s for %s, binary=%r>" % (self.__class__.__name__,
                                           addrs, self.binary)

    # {{{ Mapping interface
    def __getitem__(self, key):
        value = self.get(key)
        if value is None:
            raise KeyError(key)
        else:
            return value

    def __setitem__(self, key, value):
        if not self.set(key, value):
            raise KeyError("failed setting %r" % (key,))

    def __delitem__(self, key):
        if not self.delete(key):
            raise KeyError(key)

    def __contains__(self, key):
        return self.get(key) is not None
    # }}}

    # {{{ Behaviors
    def get_behaviors(self):
        """Gets the behaviors from the underlying C client instance.

        Reverses the integer constants for `hash` and `distribution` into more
        understandable string values. See *set_behaviors* for info.
        """
        bvrs = super(Client, self).get_behaviors()
        bvrs["hash"] = hashers_rvs[bvrs["hash"]]
        bvrs["distribution"] = distributions_rvs[bvrs["distribution"]]
        return BehaviorDict(self, bvrs)

    def set_behaviors(self, behaviors):
        """Sets the behaviors on the underlying C client instance.

        Takes care of morphing the `hash` key, if specified, into the
        corresponding integer constant (which the C client expects.) If,
        however, an unknown value is specified, it's passed on to the C client
        (where it most surely will error out.)

        This also happens for `distribution`.
        """
        behaviors = behaviors.copy()
        if behaviors.get("hash") is not None:
            behaviors["hash"] = hashers[behaviors["hash"]]
        if behaviors.get("ketama_hash") is not None:
            behaviors["ketama_hash"] = hashers[behaviors["ketama_hash"]]
        if behaviors.get("distribution") is not None:
            behaviors["distribution"] = distributions[behaviors["distribution"]]
        return super(Client, self).set_behaviors(behaviors)

    behaviors = property(get_behaviors, set_behaviors)
    @property
    def behaviours(self):
        raise AttributeError("nobody uses british spellings")
    # }}}

    def clone(self):
        obj = super(Client, self).clone()
        obj.addresses = list(self.addresses)
        obj.binary = self.binary
        return obj
