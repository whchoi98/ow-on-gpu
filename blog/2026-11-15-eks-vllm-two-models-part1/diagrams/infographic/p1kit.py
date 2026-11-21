"""Drawing helpers shared by the figures of Part 1 (f2_decision, f3_websearch)."""
from infokit import CODE_FAMILY, cw, rw, tag

EKS = "service/Amazon-Elastic-Kubernetes-Service"
EC2 = "service/Amazon-EC2"
CLIENT = "resource/Client"


def agentcore(d):
    """The AgentCore icon. The set name is the brightness of the glyph, so a light page takes the dark glyph."""
    return "agentcore-%s/Agentcore" % ("dark" if d.theme == "light" else "light")


def node(d, x, y, w, h, icon, title, sub=None, stroke="line2", sw=1.3, dash=None, box=None):
    """A component: icon, name and one line under it."""
    d.rect(x, y, w, h, rx=10, fill="panel", stroke=stroke, sw=sw, dash=dash)
    d.icon(icon, x + 14, y + h / 2 - 15, 30)
    size = 15.5
    while rw(title, size, 700) > w - 70 and size > 11:   # a long name shrinks to fit
        size -= 0.5
    d.text(x + 56, y + h / 2 + (-4 if sub else 5.5), title, size, 700, "text", box=box)
    if sub:
        d.text(x + 56, y + h / 2 + 16, sub, 12.5, 400, "muted", box=box)


def code(d, x, y, s, size, color="text2", anchor="start", box=None, weight=400):
    """D2Coding text, used only for real code, headers and paths. Returns the width."""
    d.text(x, y, s, size, weight, color, anchor, box=box, family=CODE_FAMILY)
    return cw(s, size)


def chip(d, x, y, text, color, size=13, h=28, pad=12, box=None):
    """A filled label for a model or a result. Returns the width."""
    w = rw(text, size, 700) + 2 * pad
    d.rect(x, y, w, h, rx=7, fill=color + "F", fo=0.16, stroke=color, sw=1.2)
    d.text(x + w / 2, y + h / 2 + size * 0.36, text, size, 700, color, "middle", box=box)
    return w


def code_chip(d, x, y, w, text, color="text", size=14, h=30, box=None):
    """A header or field value in D2Coding inside a plain box of width w."""
    d.rect(x, y, w, h, rx=6, fill="panel", stroke="line2", sw=1.1)
    d.text(x + w / 2, y + h / 2 + size * 0.36, text, size, 400, color, "middle", box=box, family=CODE_FAMILY)


def measured(d, x, y, label, text, box=None, size=13):
    """The orange "measured" tag followed by a value. Returns the right edge."""
    width = tag(d, x, y - 14, label, "orange", 11.5, 20, 8, box=box)
    d.text(x + width + 8, y + 0.5, text, size, 700, "text", box=box)
    return x + width + 8 + rw(text, size, 700)


def stat(d, x, y, w, h, value, lines, color, box=None, vsize=19):
    """One value with one or two lines that say what it is."""
    d.rect(x, y, w, h, rx=10, fill="panel", stroke="cardline", sw=1.2)
    d.rect(x, y + 12, 4, h - 24, rx=2, fill=color + "F")
    top = y + h / 2 - (len(lines) * 18) / 2
    d.text(x + 18, top + 4, value, vsize, 700, color, box=box)
    for index, line in enumerate(lines):
        d.text(x + 18, top + 27 + index * 18, line, 12.5, 400, "muted" if index else "text2", box=box)
