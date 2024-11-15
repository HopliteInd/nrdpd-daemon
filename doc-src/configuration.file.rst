Configuration Syntax
====================

.. index::
    single: Configuration Syntax

All configuration files have identical syntax.  This allows for templating
and overriding based on those templates. The templating is allowed by follwing
a specific processing order with the files.

The primary ``config.ini`` file is processed first.  After that the ``*.ini``
files in the ``conf.d`` directory are processed in lexical order. Each
subsequent file in this processing chain can override values defined in prior
files.

Anatomy of a configuration file
===============================

The configuration files for nrdpd are standard INI files.  The ``DEFAULT``
section is a magical section from which all others inherit.  You can use
this section to set the defaults so you don't have to replicate values in
other sections (templating).

.. code-block:: ini
    :caption: Example configuration file

    [DEFAULT]
    timeout = 10
    frequency = 60
    state = enable
    host = webserver.example.com

    [config]
    servers = https://nagios.example.com/nrdp
    token = SuperSecretToken
    host = webserver
    cacert = /etc/pki/tls/certs/example.com.CA.crt
    fqdn = webserver.example.com
    ip = 127.0.0.1

    [check:test]
    command = sh -c "echo 'Warning the sky is falling'; exit 1"

    [check:test2]
    command = sh -c "echo 'Critical the sky fell'; exit 2"

    [check:test3]
    state = disable

The only required section is the ``[config]`` section.  Obviously if you
don't have any checks, nothing will be submitted, so at least one check
should be defined.

[DEFAULT]
---------

The ``[DEFAULT]`` section is optional.  Any option set here will be the default
value for all other sections.

.. note::
    Please take note of the ``host`` option.  If you set that it will be the
    default in both the ``[config]`` section as well as in the individual
    ``[check:*]`` sections.

[config]
--------

The ``[config]`` section of the ini file is where the main options for
nrdpd are set.  The valid options are:

* **servers**: *required* List of NRDP endpoints to submit results to.  You can
    submit results to multiple servers.  The servers are separated with
    whitespace.
* **token**: *required* The NRDP authentication token.  This is necessary for
    sending results in to the service.
* **hostname**: *optional* This is the name of the host in nagios.  By default
    the library will populate this with the short name.

    For instance if your full hostname is *webserver.example.com* the library
    will poulate this with *webserver*.  If you populate the ``hostname``
    option in the ``[DEFAULT]`` section and you need to revert to the short
    name you can either explicitly use the short name or just set host to
    a blank value.

    .. code-block:: ini

        [DEFAULT]
        host = webserver.example.com

        [config]
        ; Default to what the library thinks
        hostname =
        ; Override [DEFAULT] with the short name
        hostname = webserver

* **fqdn**: *optional* This is the fully qualified domain name of the host.
    You'll want to set this if you are checking SSL certificates.  Default
    is to use what comes back from gethostname().  Many people use short names
    for this value, so it may not default to the FQDN.
* **ip**: *optional* This is the IP address for the host.  This is primarily
    used as the default value for *ip* when used for command substitution.
* **cacert**: *optional* If your nrdp endpoint is available via ``https`` and
    you don't have a public cert you may have to pass in the path to a valid
    x509 CA certificate in PEM format.

[check:SERVICE]
---------------

The ``[check:SERVICE NAME]`` sections describe the individual service checks
to run on the host.  The ``SERVICE NAME`` aspect needs to be exactly what is
defined in the nagios configuration file under the service -> name option.

.. code-block:: none
    :caption: Example nagios definition matching

    define service {
        name        SERVICE NAME
        .....
    }

Below is a full configuration example for a service check in defined for nrdpd.

.. code-block:: ini

    [check:Load Average]
    timeout = 10
    frequency = 60
    state = enable
    host = irrelevant.example.com
    command = /usr/lib64/nagios/plugins/check_load -w 15,10,5 -c 30,25,20
    hostname = scooby
    ip = 127.0.0.2

* **timeout**: *optional* If the check does not complete within ``timeout``
    seconds report the check as ``CRITICAL`` to Nagios.  The type for this
    value is float.  So anything that can reasonably be converted to a float
    is valid.

    The default value is ``10.0`` and the minimum value is ``1.0``.
* **frequency**: *optional* Define how frequent to execute the check.  The
    internal algorithm for running this attempts to define this as start
    time to start time.  The only deviation to this will be if a previous
    execution time extends past the next scheduled start time.  In this case
    you will experience an offset change to the schedule.

    The default value is ``60.0`` and the minimum value is ``10.0``.
* **state**: *optional* Determine the state of the check.  This is really only
    useful if you are planning on doing templates.  The valid values for this
    option are:

        * **enable**: *default* Enable the check to run as described.
        * **disable**: Do not run the check at all.
        * **fake**: Send fake successful results to the nagios server.  This
            option is so that you can build a generic template for disk checks
            and then for the one oddball host in a class that doesn't have the
            specified disk, you can send in happy fake results.
* **host**: *optional* This value is used in variable substitution within the
    ``command``.  Any use of ``$host`` or ``${host}`` within the command will
    be substituted with this value.

    No validation of this value is done.  So anything you put in here can
    be used generically as a variable anywhere on the command line of the
    command.
* **fqdn**: *optional* This value is used in variable substitution within the
    ``command``.  Any use of ``$fqdn`` or ``${fqdn}`` within the command will
    be substituted with this value.

    No validation of this value is done.  So anything you put in here can
    be used generically as a variable anywhere on the command line of the
    command.
* **ip**: *optional* This value is used in variable substitution within the
    ``command``.  Any use of ``$ip`` or ``${ip}`` within the command will
    be substituted with this value.  The IP must be a valid IPv4 or IPv6
    address.
* **hostname**: *optional* Override the host name that the nagios check is
    submitted on behalf of.   This allows you to monitor one host from another
    host, submitting checks on behalf of both hosts.
* **command**: *required* The nagios plugin to execute.

    Variable substitution can be done here.  Any value that matches
    ``$variable`` or ``${variable}`` will attempt to substitue the
    corresponding values in.  This feature is primarily of use to people
    using the libnrdpd library instead of nrdpd.  It allows you to customize
    things to a great extent.   If no corresponding variable is found then
    the literal ``$variable`` or ``${variable}`` will be in the command.

Deployment Recommendations
==========================

The primary recommended deployment consists of a ``config.ini`` file with just
the ``[DEFAULT]`` and ``[config]`` sections in them.   Then deploy your generic
check template as say ``conf.d/00-linux-checks.ini``, server class specific
checks in ``conf.d/50-apache-checks.ini`` and finally any machine specific
overrides or manual checks in ``conf.d/99-local.ini``.

