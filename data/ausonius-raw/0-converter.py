import re
import lxml.etree as ET

MET_MAP = {
    "A": "long",
    "T": "long",
    "b": "short",
    "c": "short",
    "X": "anceps",
    "e": "elided"
}

def parse_sy(sy):
    """1A1b1c2A -> ['A', 'b', 'c', 'A']"""
    return re.findall(r'[ATbcX]', sy)

def split_punctuation(text):
    m = re.match(r'^(.*?)([.,;:!?]+)?$', text)
    return m.group(1), m.group(2)

def convert(xml_string):
    src = ET.fromstring(xml_string)
    root = ET.Element("text")

    for line in src.xpath(".//line[@pattern!='not scanned'][@meter='P' or @meter='H']"):
        l = ET.SubElement(root, "l", n=line.attrib["name"])

        for word in line.findall("word"):
            form, punct = split_punctuation(word.text.strip())

            w = ET.SubElement(l, "w", form=form)

            if word.attrib.get("sy"):
                for q in parse_sy(word.attrib["sy"]):
                    ET.SubElement(w, "s", met=MET_MAP[q])
            elif str(word.attrib.get("mf")) in {"SY", "PE"}:
                ET.SubElement(w, "s", met=MET_MAP['e'])



            if punct:
                pc = ET.SubElement(l, "pc")
                pc.text = punct

    return ET.tostring(root, encoding=str)

# Example:
import glob
import os
for file in glob.glob("*.xml"):
    with open(file, "rb") as f:
        xml_input = f.read()
        with open(f"../ausonius-gold/{os.path.basename(file)}", "w") as f2:
            f2.write(convert(xml_input))
