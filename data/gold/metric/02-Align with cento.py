import glob
import lxml.etree as et
import re
from collections import Counter
import copy


punc = re.compile(r'[,\.‘;:\'\?!]+')


def normalize(string: str) -> str:
    return punc.sub("", string).lower().replace("v", "u").replace("j", "i").strip()

errors = Counter()
def manual_rules(left, right):
    if left == "innixa" and right == "adnixa":
        return True
    elif (left, right) == ("exanguis", "exsanguis"):
        return True
    elif (left, right) == ("lectumque", "letumque"):
        return True
    elif (left, right) == ("tremiscit", "tremescit"):
        return True
    elif (left, right) == ("inanes", "inanis"):
        return True


resource = {}
for file in glob.glob("*.xml"):
    if "cento" not in file:
        resource[file.replace(".xml", "")] = et.parse(file)

cento = et.parse("../cento.xml")


def get_text(w: et.Element):
    return "".join([s.text for s in w if s is not None and s.text])


ns = dict(namespaces={'t': "http://www.tei-c.org/ns/1.0"})

found = 0
total = 0
for l in cento.xpath("//t:l", **ns):
    for idx, seg in enumerate(l.xpath("./t:seg", **ns)):
        source = seg.attrib["source"]
        source_line = copy.deepcopy(resource[":".join(source.split(":")[:-1])]).xpath(
            f"//t:l[@n='{source}']", **ns
        )[0]
        source_words = list(source_line.xpath("t:w", **ns))

        for w in seg.xpath("t:w", **ns):
            idx = 0
            if w.attrib["pos"] == "PUNC":
                w.tag = "pc"
                w.attrib.clear()
                continue
            elif w.text.startswith("{"):
                continue
            elif not w.text:
                continue

            total += 1

            before_found = found + 0
            n_w = normalize(w.text)
            while idx < len(source_words):
                sylls = source_words[idx].attrib['form']
                n_s = normalize(sylls)
                if n_s == n_w or manual_rules(n_w, n_s):
                    w.attrib["form"] = "" + w.text
                    w.text = ""
                    for child in source_words[idx]:
                        w.append(child)
                    source_words.pop(idx)
                    found += 1
                    idx += 1
                    break
                idx += 1

            if before_found == found:
                print(f"Issue on {source}")
                w.attrib["notfound"] = 'true'
                errors[source] += 1

print(found/total)

with open("cento-aligned.xml", "w") as f:
    f.write(et.tostring(cento, encoding=str))

for i, v in errors.most_common(50):
    if v > 1:
        print(i, v)

print(sum(errors.values()))