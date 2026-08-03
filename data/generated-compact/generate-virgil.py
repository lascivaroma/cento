import os.path as op
import lxml.etree as et

root = op.abspath(op.join(op.dirname(__file__), "..", ".."))

out = et.Element("text")

work = et.Element("div")
work.attrib["type"] = "work"
work.attrib["title"] = "Virgil (Aeneid)"
work.attrib["n"] = "phi0690.phi003"

xml = et.parse(op.join(root, "stylometry", "raw", "vergil_pedecerto", "aeneid.xml"))
for division in xml.xpath("//division"):
    poem = division.attrib["title"]
    division.tag = "div"
    work.append(division)
    for line in division.xpath("line"):
        line.attrib["n"] = f"urn:cts:latinLit:phi0690.phi003:{division.attrib['title']}.{line.attrib['name']}"
out.append(work)

####################################
# Eclogues
work = et.Element("div")
work.attrib["type"] = "work"
work.attrib["title"] = "Virgil (Eclogues)"
work.attrib["n"] = "phi0690.phi001"

xml = et.parse(op.join(root, "stylometry", "raw", "vergil_pedecerto", "eclogues.xml"))
for division in xml.xpath("//division"):
    poem = division.attrib["title"]
    division.tag = "div"
    work.append(division)
    for line in division.xpath("line"):
        line.attrib["n"] = f"urn:cts:latinLit:phi0690.phi001:{division.attrib['title']}.{line.attrib['name']}"
out.append(work)


####################################
# Georgics
work = et.Element("div")
work.attrib["type"] = "work"
work.attrib["title"] = "Virgil (Georgics)"
work.attrib["n"] = "phi0690.phi002"

xml = et.parse(op.join(root, "stylometry", "raw", "vergil_pedecerto", "georgics.xml"))
for division in xml.xpath("//division"):
    poem = division.attrib["title"]
    division.tag = "div"
    work.append(division)
    for line in division.xpath("line"):
        line.attrib["n"] = f"urn:cts:latinLit:phi0690.phi002:{division.attrib['title']}.{line.attrib['name']}"
out.append(work)

with open(op.join(op.dirname(__file__), "virgil-compact.xml"), "w") as f:
    f.write(et.tostring(out, encoding=str))

