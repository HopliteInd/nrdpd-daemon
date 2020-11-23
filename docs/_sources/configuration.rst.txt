Configuration Guide
===================

.. toctree::

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


Configuring nrdpd as a service
------------------------------

In order to work as designed ``nrdpd`` needs to be installed as a service
on your platform.  The gist of it is to run ``nrdpd`` as a background process,
so any method you have of doing that should be valid.

Listed below are just a few possibilities.

Linux
^^^^^

rc.local
""""""""

Adding the following line to /etc/rc.local should start nrdpd safely in the
background.

.. code:: bash

    /usr/bin/nrdpd </dev/null >/dev/null 2>&1 &

In this case make sure you have the trailing ``&`` otherwise your system
will hang on boot at that point.


systemd
"""""""

Creaet a systmed file named ``/lib/systemd/system/nrdpd.service`` with the
following contents:

.. code:: ini

    [Unit]
    Description=Nagios Remote Data Processing Daemon
    Documentation=https://nrdpd-daemon.readthedocs.io/
    After=network.target

    [Service]
    User=root
    Group=root
    ExecStart=/usr/bin/nrdpd

    [Install]
    WantedBy=multi-user.target


Windows
^^^^^^^

.. todo:: Add creating service in windows



