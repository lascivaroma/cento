import glob
import lxml.etree as et
import re


punc = re.compile(r'[,\.‘;:]+')


resource = {}
for file in glob.glob("*.xml"):
    resource[file.replace(".xml", "")] = et.parse(file)

cento = et.parse("../cento.xml")


def get_text(w: et.Element):
    return "".join([s.text for s in w if s and s.text])


ns = dict(namespaces={'t': "http://www.tei-c.org/ns/1.0"})

found = 0
total = 0
for l in cento.xpath("//t:l", **ns):
    for idx, seg in enumerate(l.xpath("./t:seg", **ns)):
        source = seg.attrib["source"]
        source_line = resource[":".join(source.split(":")[:-1])].xpath(
            f"//t:l[@n='{source}']", **ns
        )[0]
        source_words = list(source_line.xpath("t:w", **ns))

        idx = 0
        for w in seg.xpath("t:w", **ns):
            if w.attrib["pos"] == "PUNC":
                w.tag = "pc"
                w.attrib.clear()
                continue

            total += 1

            if idx < len(source_words):
                sylls = get_text(source_words[idx])
                print(sylls.lower(), punc.sub("", sylls.lower()))
                if punc.sub("", sylls.lower()) == w.text.lower():
                    w.attrib["form"] = "" + w.text
                    w.text = ""
                    for child in source_words[idx]:
                        w.append(child)
                    idx += 1
                    found += 1

        break

print(found/total)