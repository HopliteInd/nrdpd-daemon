.. contents::
    :depth: 2

###################
Configuration Guide
###################

Configuration guide for the nrdpd daemon and libnrdpd.


Configuration Files
===================

The default locations for the nrdpd files vary depending on platform.

Windows
-------

The configuration files on the Windows platform will be installed in the same
location as the executables.

.. code:: none

    # Base configuration file
    C:\Program Files\Python38\Scripts\config.ini

    # Additional configuration files
    c:\Program Files\Python38\Scripts\conf.d\*.ini

Posix
-----

The configuration files on Posix platforms (Linux, \*BSD,  Mac OS) will be
installed in ``/etc/nrdpd``.

.. code:: none

    # Base configuration file
    /etc/nrdpd/config.ini

    # Additional configuration files
    /etc/nrdpd/conf.d/*.ini

Configuration Syntax
====================

.. toctree::
    :caption: Please see the following for configuration syntax

    Overview <configuration.file>



.. _service:

Configuring nrdpd as a service
==============================

In order to work as designed ``nrdpd`` needs to be installed as a service
on your platform.  The gist of it is to run ``nrdpd`` as a background process,
so any method you have of doing that should be valid.

Listed below are just a few possibilities.

Linux
-----

rc.local
^^^^^^^^

Adding the following line to /etc/rc.local should start nrdpd safely in the
background.

.. code-block:: bash

    /usr/bin/nrdpd </dev/null >/dev/null 2>&1 &

In this case make sure you have the trailing ``&`` otherwise your system
will hang on boot at that point.


systemd
^^^^^^^

Creaet a systmed file named ``/lib/systemd/system/nrdpd.service`` with the
following contents:

.. code-block:: ini

    [Unit]
    Description=Nagios Remote Data Processing Daemon
    After=network.target

    [Service]
    Type=simple
    # the specific user that our service will run as
    User=root
    Group=root
    RuntimeDirectory=nrdpd
    PidFile=/run/nrdpd.pid
    ExecStart=/usr/bin/nrdpd
    ExecReload=/bin/kill -s TERM $MAINPID
    KillMode=mixed
    TimeoutStopSec=5

    [Install]
    WantedBy=multi-user.target


Windows
-------

To install nrdpd as a service in windows it is recommended that you use a
service manager such as `NSSM <http://nssm.cc>`_.

.. code-block:: none
    :caption: Installing nrdbd as a service with nssm

    nssm install nrdbd "C:\Program Files\Python38\Scripts\nrdbd.exe"
    nssm start nrdbd

