Change fragments
================

Every pull request that changes behaviour, the build or the docs adds one file
here instead of editing ``docs/changelog.rst``, so PRs do not conflict. At
release time ``bin/changelog build X.Y.Z --write`` turns the fragments into the
change log entry and the release commit deletes them.

Name
    ``<number>.<category>.rst``, where the number is the pull request or the
    issue it fixes. With no number, use ``+<word>.<category>.rst``, for example
    ``+sasl-wheels.build.rst``.

Category
    ``breaking`` (can break existing code), ``new``, ``fix``, ``build``
    (build and platforms) or ``docs``. They appear in that order.

Content
    The text of one bullet, as reST, without the leading ``- ``. It may span
    lines; the script rewraps it to 80 columns. If the file name has a number
    and the text does not mention it, ``(#N)`` is added.

    Write for the person upgrading, not for the reviewer: say what behaves
    differently, what they should do about it and what to watch out for (a
    changed exception, a new default, a dropped platform), and why. "Fixed
    reference leak in ``foo``" is a code change; "``foo`` no longer grows the
    process by one reference per key on every call" is a consequence. Do not
    describe changes inside libmemcached itself.

Example, ``docs/changes.d/202.breaking.rst``::

    A negative expiry time now raises ``ValueError`` in ``set`` and friends.
    It used to be turned silently into a huge number.

``bin/changelog check`` validates the names and contents; CI runs it. A PR
that touches ``src/``, ``setup.py`` or ``.github/`` without a fragment fails
CI, unless its description has a line saying ``no-changelog``.
