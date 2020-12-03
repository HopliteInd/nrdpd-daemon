Nagios Remote Data Protocol Daemon
==================================

The ``nrdpd`` program is used as a passive monitoring agent for Nagios.  It
will use regular Nagios plugins to perform system checks and submit those
results to your monitoring server(s) via the NRDP protocol.

This package contains both the ``nrdpd`` service and a Python library that
you can integrate with.


.. toctree::
   :maxdepth: 2
   :caption: Components:

   configuration
   nrdpd
   libnrdpd

Installation
============

The nrdpd-daemon software can be installed with ``pip`` or doing a manual
install from source. You can download the source from 
`PyPi <https://pypi.org/project/nrdp-daemon/#files>`_ or 
`GitHub <https://github.com/HopliteInd/nrdpd-daemon/releases/>`_.  

.. code-block:: bash
    :caption: System installation via pip

    pip install nrdp-daemon

If you want to test it out as a user prior to polluting your system:

.. code-block:: bash
    :caption: User installation via pip

    pip install --user nrdp-daemon


Windows Notes
-------------

In windows you may need to add the Python paths to your ``Path``.  To do
this run the windows search for ``environment``. Click on the **Edit the
system environment variables** option.  You'll need to run this as
an adminstrative user.  This should bring up the **System Properties**
dialog.  Click on the ``Environment Variables`` button near the bottom.

You'll want to edit the ``Path`` variable.  Using Python version 3.8 as an
example, you'll need to make sure that the following are in the Path:

* ``C:\\Program Files\\Python38``
* ``C:\\Program Files\\Python38\\Scripts``



    
