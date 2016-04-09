import sys
import zlib
import imp

z = zlib.decompressobj()
while 1:
    name = stdin.readline().strip()
    if name:
        name = name.decode("ASCII")

        nbytes = int(stdin.readline())
        if verbosity >= 2:
            sys.stderr.write('server: assembling {0!r} ({1:d} bytes)\n'.format(name, nbytes))
        content = z.decompress(stdin.read(nbytes))

        module = imp.new_module(name)
        parent, _, parent_name = name.rpartition(".")
        if parent != "":
            setattr(sys.modules[parent], parent_name, module)

        code = compile(content, name, "exec")
        exec(code, module.__dict__)
        sys.modules[name] = module
    else:
        break

sys.stderr.flush()
sys.stdout.flush()

import sshuttle.helpers
sshuttle.helpers.verbose = verbosity

import sshuttle.cmdline_options as options
from sshuttle.server import main
main(options.latency_control)
