import ctypes, time, sys, subprocess, os

x11 = ctypes.CDLL('libX11.so.6')
xt = ctypes.CDLL('libXtst.so.6')
x11.XOpenDisplay.restype = ctypes.c_void_p
d = x11.XOpenDisplay(None)
x11.XStringToKeysym.restype = ctypes.c_ulong
x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
x11.XKeysymToKeycode.restype = ctypes.c_ubyte
x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
xt.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
xt.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
x11.XWarpPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_int, ctypes.c_uint, ctypes.c_uint, ctypes.c_int, ctypes.c_int]
x11.XDefaultRootWindow.restype = ctypes.c_ulong
x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
x11.XFlush.argtypes = [ctypes.c_void_p]
x11.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
x11.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]

def focus(wid):
    x11.XRaiseWindow(d, wid)
    x11.XSetInputFocus(d, wid, 1, 0)
    x11.XFlush(d)
    time.sleep(0.3)

def key(k, hold_ms):
    kc = x11.XKeysymToKeycode(d, x11.XStringToKeysym(k.encode()))
    xt.XTestFakeKeyEvent(d, kc, 1, 0); x11.XFlush(d)
    time.sleep(hold_ms / 1000.0)
    xt.XTestFakeKeyEvent(d, kc, 0, 0); x11.XFlush(d)

def click(x, y):
    root = x11.XDefaultRootWindow(d)
    x11.XWarpPointer(d, 0, root, 0, 0, 0, 0, x, y); x11.XFlush(d); time.sleep(0.15)
    xt.XTestFakeButtonEvent(d, 1, 1, 0); x11.XFlush(d); time.sleep(0.08)
    xt.XTestFakeButtonEvent(d, 1, 0, 0); x11.XFlush(d)

def move(x, y):
    root = x11.XDefaultRootWindow(d)
    x11.XWarpPointer(d, 0, root, 0, 0, 0, 0, x, y); x11.XFlush(d); time.sleep(0.1)

def button(number, down):
    xt.XTestFakeButtonEvent(d, number, 1 if down else 0, 0); x11.XFlush(d); time.sleep(0.08)

def rclick(x, y):
    move(x, y)
    button(3, True)
    button(3, False)

def rdrag(x1, y1, x2, y2):
    move(x1, y1)
    button(3, True)
    steps = 8
    for i in range(1, steps + 1):
        move(x1 + (x2 - x1) * i // steps, y1 + (y2 - y1) * i // steps)
    button(3, False)

def bothclick(x, y, hold_ms):
    move(x, y)
    button(1, True)
    button(3, True)
    time.sleep(hold_ms / 1000.0)
    button(3, False)
    button(1, False)

def shot(path):
    wid = None
    proc = subprocess.run(['xwininfo', '-root', '-tree'], capture_output=True, text=True, env={**os.environ, 'DISPLAY': ':0'})
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        print('ERROR: xwininfo failed', file=sys.stderr)
        return
    out = proc.stdout
    for line in out.splitlines():
        if 'StarCraft II' in line:
            wid = line.split()[0]
            break
    if not wid:
        print('no window'); return
    subprocess.run(['xwd', '-id', wid, '-out', path + '.xwd'], env={**os.environ, 'DISPLAY': ':0'})
    ffmpeg = os.environ.get('FFMPEG', 'ffmpeg')
    subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-i', path + '.xwd', path])

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'hold':
        key(sys.argv[2], int(sys.argv[3]))
    elif cmd == 'click':
        click(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == 'shot':
        shot(sys.argv[2])
    elif cmd == 'rclick':
        rclick(int(sys.argv[2]), int(sys.argv[3]))
    elif cmd == 'rdrag':
        rdrag(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]))
    elif cmd == 'both':
        bothclick(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
    print('ok', cmd)

if len(sys.argv) > 1 and sys.argv[1] == "auto":
    import re
    proc = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True, text=True, env={**os.environ, "DISPLAY": ":0"})
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        print("ERROR: xwininfo failed", file=sys.stderr)
        raise SystemExit(1)
    out = proc.stdout
    geo = None
    wid = None
    for line in out.splitlines():
        if "StarCraft II" in line:
            try:
                wid = int(line.split()[0], 16)
            except ValueError:
                wid = None
            m = re.search(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", line)
            if m:
                geo = tuple(int(v) for v in m.groups())
            break
    if wid:
        focus(wid)
    if geo:
        w, h, x, y = geo
        click(x + w // 2, y + h // 2)
    time.sleep(0.5)
    key("space", 150)
    time.sleep(0.5)
    key("Return", 150)
    print("auto ok")
