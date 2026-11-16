Removed the C extension's leftover compatibility code for Python 2 and
Python 3 releases older than 3.11, which are no longer supported. You should
notice nothing: that code only did anything on those Pythons. The one
difference is that the extension now imports ``pickle`` directly instead of
first trying a module called ``cPickle``, which Python 3 does not have; if
something on your ``sys.path`` provides a ``cPickle`` module, pylibmc no longer
uses it for serialisation.
