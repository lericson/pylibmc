Python 3.8, 3.9 and 3.10 and PyPy 3.9 and 3.10 are no longer supported: they
have reached end of life. pylibmc now requires CPython 3.11 or later, or PyPy
3.11, and no wheels are built for the older versions. pip on an older Python
keeps installing pylibmc 1.7.x; pin ``pylibmc<1.8`` if your environment
resolves packages some other way.
