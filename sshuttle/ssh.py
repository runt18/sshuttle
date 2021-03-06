import sys
import os
import re
import socket
import zlib
import imp
import subprocess as ssubprocess
import sshuttle.helpers as helpers
from sshuttle.helpers import debug2


def readfile(name):
    tokens = name.split(".")
    f = None

    token = tokens[0]
    token_name = [token]
    token_str = ".".join(token_name)

    try:
        f, pathname, description = imp.find_module(token_str)

        for token in tokens[1:]:
            module = imp.load_module(token_str, f, pathname, description)
            if f is not None:
                f.close()

            token_name.append(token)
            token_str = ".".join(token_name)

            f, pathname, description = imp.find_module(
                token, module.__path__)

        if f is not None:
            contents = f.read()
        else:
            contents = ""

    finally:
        if f is not None:
            f.close()

    return contents.encode("UTF8")


def empackage(z, name, data=None):
    if not data:
        data = readfile(name)
    content = z.compress(data)
    content += z.flush(zlib.Z_SYNC_FLUSH)

    return b'{0!s}\n{1:d}\n{2!s}'.format(name.encode("ASCII"), len(content), content)


def connect(ssh_cmd, rhostport, python, stderr, options):
    portl = []

    if (rhostport or '').count(':') > 1:
        if rhostport.count(']') or rhostport.count('['):
            result = rhostport.split(']')
            rhost = result[0].strip('[')
            if len(result) > 1:
                result[1] = result[1].strip(':')
                if result[1] is not '':
                    portl = ['-p', str(int(result[1]))]
        # can't disambiguate IPv6 colons and a port number. pass the hostname
        # through.
        else:
            rhost = rhostport
    else:  # IPv4
        l = (rhostport or '').split(':', 1)
        rhost = l[0]
        if len(l) > 1:
            portl = ['-p', str(int(l[1]))]

    if rhost == '-':
        rhost = None

    z = zlib.compressobj(1)
    content = readfile('sshuttle.assembler')
    optdata = ''.join("{0!s}={1!r}\n".format(k, v) for (k, v) in list(options.items()))
    optdata = optdata.encode("UTF8")
    content2 = (empackage(z, 'sshuttle') +
                empackage(z, 'sshuttle.cmdline_options', optdata) +
                empackage(z, 'sshuttle.helpers') +
                empackage(z, 'sshuttle.ssnet') +
                empackage(z, 'sshuttle.hostwatch') +
                empackage(z, 'sshuttle.server') +
                b"\n")

    pyscript = r"""
                import sys;
                verbosity={0:d};
                stdin=getattr(sys.stdin,"buffer",sys.stdin);
                exec(compile(stdin.read({1:d}), "assembler.py", "exec"))
                """.format(helpers.verbose or 0, len(content))
    pyscript = re.sub(r'\s+', ' ', pyscript.strip())

    if not rhost:
        # ignore the --python argument when running locally; we already know
        # which python version works.
        argv = [sys.argv[1], '-c', pyscript]
    else:
        if ssh_cmd:
            sshl = ssh_cmd.split(' ')
        else:
            sshl = ['ssh']
        if python:
            pycmd = "'{0!s}' -c '{1!s}'".format(python, pyscript)
        else:
            pycmd = ("P=python3.5; $P -V 2>/dev/null || P=python; "
                     "exec \"$P\" -c '%s'") % pyscript
        argv = (sshl +
                portl +
                [rhost, '--', pycmd])
    (s1, s2) = socket.socketpair()

    def setup():
        # runs in the child process
        s2.close()
    s1a, s1b = os.dup(s1.fileno()), os.dup(s1.fileno())
    s1.close()
    debug2('executing: {0!r}\n'.format(argv))
    p = ssubprocess.Popen(argv, stdin=s1a, stdout=s1b, preexec_fn=setup,
                          close_fds=True, stderr=stderr)
    os.close(s1a)
    os.close(s1b)
    s2.sendall(content)
    s2.sendall(content2)
    return p, s2
