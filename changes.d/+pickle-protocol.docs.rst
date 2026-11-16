The ``pickle_protocol`` behavior is documented for today's Pythons: the advice
about Python 2 is gone, and the documentation suggests pinning the protocol to
a number (for example ``5``) when more than one Python version shares a cache,
so a newer Python's default cannot write pickles that older ones cannot read.
