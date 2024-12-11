import lxml.etree as et
import glob
import tqdm
import re
import unicodedata

macro = unicodedata.normalize("NFKD", "ī")[-1]

ns = et.FunctionNamespace("https://foo.bar")

@ns
def normalize(context, a):
	return [
		unicodedata.normalize("NFD", el).replace(macro, "")
		for el in a
	]


title = re.compile(r"([a-z]+)(\d+)\.html")
xsl = et.XSLT(et.parse("01-XSLT.xsl"))

files = {
	"aen": "urn:cts:latinLit:phi0690.phi003",
	"eclogue": "urn:cts:latinLit:phi0690.phi001",
	"geo": "urn:cts:latinLit:phi0690.phi002"
}

output = {
	"aen": [],
	"eclogue": [],
	"geo": [],
}

for file in tqdm.tqdm(sorted(glob.glob("*.html"), key=lambda x: title.findall(x))):
	((text, book), ) = title.findall(file)
	xml = et.parse(file)
	xml = xsl(xml)
	for idx, l in enumerate(xml.xpath("//t:l", namespaces={'t': "http://www.tei-c.org/ns/1.0"})):
		l.attrib["n"] = f"{files[text]}:{book}.{idx+1}"
	output[text].extend(xml.xpath("//t:l", namespaces={'t': "http://www.tei-c.org/ns/1.0"}))

for file in output:
	xml = et.fromstring("<root xmlns='http://www.tei-c.org/ns/1.0'></root>")
	for l in output[file]:
		xml.append(l)
	with open(files[file]+".xml", "w") as f:
		f.write(et.tostring(xml, encoding=str))

