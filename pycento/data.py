import lxml.etree as et
import os.path as op
from dataclasses import dataclass
from typing import List


_gold = op.join(op.abspath(op.dirname(__file__)), "..", "data", "gold")
_ns = {"t": "http://www.tei-c.org/ns/1.0"}


@dataclass
class Syllable:
	text: str
	length: str

	@property
	def nice_length(self):
		if self.length == "short":
			return 1
		elif self.length == "long":
			return 2
		else:
			return 0

	def __repr__(self):
		return f"{self.nice_length}"


@dataclass
class Word:
	text: str
	lemma: str
	pos: str
	morph: str
	syllables: List[Syllable]
	caesura_after: bool = False

	def __repr__(self):
		return " ".join(map(repr, self.syllables)) if self.syllables else self.text

@dataclass
class Segment:
	source: str
	words: List[Word]
	continued: bool = False

	@property
	def normalized_source(self):
		*_, work, psg = self.source.split(":")
		work = {
			"phi0690.phi003": "Ae.",
			"phi0690.phi001": "B.",
			"phi0690.phi002": "G."

		}[work]
		return f"{work}, {psg}" 


	def __repr__(self):
		return f"[{self.normalized_source}] " + " ".join([repr(w) or "()" for w in self.words])

@dataclass
class Line:
	idx: int
	segments: List[Segment]
	ws: List[Word] = None
	ref: str = None

	@property
	def words(self) -> List[Word]:
		if self.segments:
			return [
				word
				for seg in self.segments
				for word in seg.words
			]
		else:
			return self.ws

	def __repr__(self):
		if self.segments:
			return f"<{self.idx}> " + " ".join([repr(seg) for seg in self.segments])
		else:
			return f"<{self.idx}> " + " ".join([repr(seg) for seg in self.words])

	


def parse_cento(file, punc=False) -> List[Line]:
	""" Parses the Cento and returns a list of Lines

	:param punc: Retrieve punctuation (Filtered by default)
	"""
	data = et.parse(file)
	lines = []
	for idx, line in enumerate(data.xpath("//t:l", namespaces=_ns)):
		segs = []
		for seg in line.xpath("./t:seg", namespaces=_ns):
			ws = []
			for word in seg.xpath("./t:w", namespaces=_ns):
				if not punc and word.attrib["pos"] == "PUNC":
					continue
				text = word.attrib.get("form", word.text)
				syllables = [
					Syllable(text=syll.text, length=syll.attrib.get("met"))
					for syll in word.xpath("./t:s", namespaces=_ns)
				]
				try:

					ws.append(
						Word(
							text if not text.startswith("{") else "",
							word.attrib["lemma"], word.attrib["pos"], word.attrib["msd"],
							syllables=syllables
						)

					)
				except Exception as E:
					print(et.tostring(word, encoding=str))
			segs.append(
				Segment(
					source=seg.attrib["source"],
					continued="type" in seg.attrib,
					words=ws
				)
			)
		lines.append(
			Line(
				idx+1,
				segments=segs
			)
		)
	return lines


def parse(file, punc=False) -> List[Line]:
	""" Parses the Cento and returns a list of Lines

	:param punc: Retrieve punctuation (Filtered by default)
	"""
	data = et.parse(file)
	# Support both TEI-namespaced and plain XML (some Ausonius files lack namespace)
	_line_nodes = data.xpath("//t:l", namespaces=_ns) or data.xpath("//l")
	lines = []
	for idx, line in enumerate(_line_nodes):
		ns = _ns if line.nsmap.get(None) == _ns["t"] else {}
		_w = f"t:w" if ns else "w"
		_s = f"t:s" if ns else "s"
		_caesura = f"t:caesura" if ns else "caesura"
		ws = []
		for word in line.xpath(f"./{_w}", namespaces=ns):
			text = word.attrib.get("form", word.text)
			sylls = word.xpath(f"./{_s}", namespaces=ns)
			syllables = [
				Syllable(text=syll.text, length=syll.attrib.get("met"))
				for syll in sylls
			]
			has_caesura = any(
				len(syll.xpath(f"./{_caesura}", namespaces=ns)) > 0
				for syll in sylls
			)
			ws.append(
				Word(
					text if not text or not text.startswith("{") else "",
					word.attrib.get("lemma"), word.attrib.get("pos"), word.attrib.get("msd"),
					syllables=syllables,
					caesura_after=has_caesura,
				)
			)
		lines.append(
			Line(
				idx+1,
				segments=[],
				ws=ws,
				ref=line.attrib.get("n", str(idx+1)),
			)
		)
	return lines


if __name__ == "__main__":
	# For debug purposes
	for i in (parse_cento(op.join(_gold, "metric", "cento-aligned.xml"))):
		print(i)
	for i in (parse(op.join(_gold, "..", "ausonius-gold", "AVSON-epig.xml"))):
		print(i)