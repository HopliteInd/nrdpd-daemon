Configuration Guide
===================

.. toctree::
    :maxdepth: 1


Configuration guide for the nrdpd daemon and libnrdpd.

Configuration Files
-------------------

The default locations for the nrdpd files vary depending on platform.

Windows
^^^^^^^

The configuration files on the Windows platform will be installed in the same
location as the executables.

.. code:: none

    # Base configuration file
    C:\Program Files\nrdpd\config.ini

    # Additional configuration files
    c:\Program Files\nrdpd\conf.d\*.ini

Posix
^^^^^

The configuration files on Posix platforms (Linux, \*BSD,  Mac OS) will be
installed in ``/etc/nrdpd``.

.. code:: none

    # Base configuration file
    /etc/nrdpd/config.ini

    # Additional configuration files
    /etc/nrdpd/conf.d/*.ini


.. todo:: Add creating service in windows

.. todo:: Add creating service in linux

