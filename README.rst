`pylibmc` is a Python client for `memcached <http://memcached.org/>`_ written in C.

See `the documentation at sendapatch.se/projects/pylibmc/`__ for more information.

__ http://sendapatch.se/projects/pylibmc/

.. image:: https://travis-ci.org/lericson/pylibmc.png?branch=master
   :target: https://travis-ci.org/lericson/pylibmc

New in version 1.5.0
====================

This release fixes critical memory leaks in common code paths introduced in
1.4.2. Also fixes a critical bug in a corner of the zlib inflation code, where
prior memory errors would trigger a double free. Thank you to everybody
involved in the making of this release, and especially `Eau de Web`__, without
their contributions, this release and the bug fixes it contains wouldn't have
been so expedient.

__ http://www.eaudeweb.ro/

.. comment: 1.5.x should have been an extension to 1.4.x, therefore it's best
   to keep the 1.4.x release announcement below.

New in version 1.4.0
====================

Brace yourself, Python 3.x support has come!

Thanks to everybody involved in this project; this release involves less
authors but **a lot** more work per person. Thanks especially to Harvey Falcic
for the work he put in, without which there wouldn't be any Python 3.x support.
Also thanks to Sergey Pashinin for the initial stab at the problem.

Other than that, we had miscellaneous bug fixes, testing improvements, and
documentation updates.

Last but not least I would like to ask for your support in this project, either
by helping out with development, testing, documentation or anything at all; or
simply by donating some `magic internet money`__ to the project's Bitcoin
address `12dveKhqiJWCY8zXT4kaHdHELXPeGAUo9h`__.

__ http://static.adzerk.net/Advertisers/5af77cf0094d4303bb308b955dd05992.jpg
__ bitcoin:12dveKhqiJWCY8zXT4kaHdHELXPeGAUo9h

License
=======

Released under the BSD 3-clause license; see `LICENSE <LICENSE>`_ for details.

Maintainer
==========

- Website: `sendapatch.se/ <http://sendapatch.se/>`_
- Github: `github.com/lericson <http://github.com/lericson>`_
- IRC: ``lericson`` in ``#sendapatch`` on ``chat.freenode.net``
- E-mail: ``ludvig`` at ``sendapatch.se``

------

.. image:: http://www.smbc-comics.com/comics/20110908.gif
   :target: http://www.smbc-comics.com/index.php?db=comics&id=2362
   :align: center
   :title: Look ma, we're famous!
