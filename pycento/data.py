import lxml.etree as et
import os.path as op
from dataclasses import dataclass
from typing import List


_gold = op.join(op.abspath(op.dirname(__file__)), "..", "data", "gold")
_ns = {"t": "http://www.tei-c.org/ns/1.0"}


@dataclass
class Word:
	text: str
	lemma: str
	pos: str
	morph: str

	def __repr__(self):
		return self.text

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

	@property
	def words(self) -> List[Word]:
		return [
			word
			for seg in self.segments
			for word in seg.words
		]

	def __repr__(self):
		return f"<{self.idx}> " + " ".join([repr(seg) for seg in self.segments])
	


def parse(punc=False) -> List[Line]:
	""" Parses the Cento and returns a list of Lines

	:param punc: Retrieve punctuation (Filtered by default)
	"""
	data = et.parse(op.join(_gold, "cento.xml"))
	lines = []
	for idx, line in enumerate(data.xpath("//t:l", namespaces=_ns)):
		segs = []
		for seg in line.xpath("./t:seg", namespaces=_ns):
			ws = []
			for word in seg.xpath("./t:w", namespaces=_ns):
				if not punc and word.attrib["pos"] == "PUNC":
					continue
				ws.append(
					Word(
						word.text if not word.text.startswith("{") else "",
						word.attrib["lemma"], word.attrib["pos"], word.attrib["msd"])
				)
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




if __name__ == "__main__":
	# For debug purposes
	for i in (parse()):
		print(i)