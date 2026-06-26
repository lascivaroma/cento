"""Apply cento.xsl to data/gold/cento.xml and write cent.html."""

import os.path as op
import lxml.etree as et

_ROOT = op.dirname(op.abspath(__file__))

xsl = et.parse(op.join(_ROOT, "..", "cento.xsl"))
xml = et.parse(op.join(_ROOT, "..", "data", "gold", "cento.xml"))
result = et.XSLT(xsl)(xml)

out = op.join(_ROOT, "cent.html")
with open(out, "wb") as f:
    f.write(et.tostring(result, pretty_print=True))
print(f"Wrote {out}")
