#!/usr/bin/env python
import socket
import select
import struct
import time

listener = socket.socket()
listener.bind(('127.0.0.1', 0))
listener.listen(500)

servers = []
clients = []
remain = {}

NUMCLIENTS = 50
count = 0


while 1:
    if len(clients) < NUMCLIENTS:
        c = socket.socket()
        c.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        c.bind(('0.0.0.0', 0))
        c.connect(listener.getsockname())
        count += 1
        if count >= 16384:
            count = 1
        print('cli CREATING {0:d}'.format(count))
        b = struct.pack('I', count) + 'x' * count
        remain[c] = count
        print('cli  >> {0!r}'.format(len(b)))
        c.send(b)
        c.shutdown(socket.SHUT_WR)
        clients.append(c)
        r = [listener]
        time.sleep(0.1)
    else:
        r = [listener] + servers + clients
    print('select({0:d})'.format(len(r)))
    r, w, x = select.select(r, [], [], 5)
    assert(r)
    for i in r:
        if i == listener:
            s, addr = listener.accept()
            servers.append(s)
        elif i in servers:
            b = i.recv(4096)
            print('srv <<  {0!r}'.format(len(b)))
            if i not in remain:
                assert(len(b) >= 4)
                want = struct.unpack('I', b[:4])[0]
                b = b[4:]
                # i.send('y'*want)
            else:
                want = remain[i]
            if want < len(b):
                print('weird wanted {0:d} bytes, got {1:d}: {2!r}'.format(want, len(b), b))
                assert(want >= len(b))
            want -= len(b)
            remain[i] = want
            if not b:  # EOF
                if want:
                    print('weird: eof but wanted {0:d} more'.format(want))
                    assert(want == 0)
                i.close()
                servers.remove(i)
                del remain[i]
            else:
                print('srv  >> {0!r}'.format(len(b)))
                i.send('y' * len(b))
                if not want:
                    i.shutdown(socket.SHUT_WR)
        elif i in clients:
            b = i.recv(4096)
            print('cli <<  {0!r}'.format(len(b)))
            want = remain[i]
            if want < len(b):
                print('weird wanted {0:d} bytes, got {1:d}: {2!r}'.format(want, len(b), b))
                assert(want >= len(b))
            want -= len(b)
            remain[i] = want
            if not b:  # EOF
                if want:
                    print('weird: eof but wanted {0:d} more'.format(want))
                    assert(want == 0)
                i.close()
                clients.remove(i)
                del remain[i]
listener.accept()
