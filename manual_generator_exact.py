import random
import re
import tqdm
import lxml.etree as et

from dataclasses import dataclass
from typing import List, Counter
from functools import lru_cache
from pycento.elision import check_elision, ElisionResult
from tabulate import tabulate

xml_gold = et.parse("data/generated-compact/cento-compact.xml")
_check = True
_VOWELS = set("aeiouAEIOU")

@dataclass
class Segment:
    scan: str = ""
    start_a_line: bool = False # Whether the segment starts a line
    more_than_a_line: bool = False

    @property
    def length(self):
        # ToDo for loose
        return "int"


def strip_punct(word_tag):
    return re.sub("\W", "", word_tag.text)

@lru_cache(maxsize=None)
def letters_to_ux(word1, word2):
    return re.sub(
        r"[a-z]", "u",
        re.sub(
            r"[A-Z]", "-",
            re.sub(r"\d+", "", word1.attrib["sy"]+word1.attrib["sy"])
        )
    )

@lru_cache(maxsize=None)
def _elision(w1: str, w2: str) -> ElisionResult:
    return check_elision(w1, w2)
    return Scansion().first_word_elided(sequence)

class NotFoundCandidate(ValueError):
    pass

@lru_cache(maxsize=None)
def _tail_scan_matching(line, scan):
    # Scan the tail of the line, returns the words if it matches
    line_scan = _line_scan(line)
    if not line_scan.endswith(scan):
        return None

    temp_scan = ""
    words = []
    for elem in line.xpath("./word")[::-1]:
        temp_scan = elem.attrib["sy"] + temp_scan
        words.append(elem)
        if temp_scan.endswith(scan):  # stop once one contains the other
            break

    if temp_scan == scan:
        return words[::-1]

    return None

@lru_cache(maxsize=None)
def _line_scan(line):
    return "/" + "".join(w.attrib.get("sy", "") for w in line.xpath("./word"))

@lru_cache(maxsize=None)
def _w_to_xml(word):
    return et.fromstring(word)

@lru_cache(maxsize=None)
def _line_to_string(line) -> List[str]:
    return [
        et.tostring(word, encoding=str).strip() for word in line.xpath("./word")
    ]

template: List[Segment] = []

for row in xml_gold.xpath("//line"):
    segments = row.xpath("./milestone")
    nb_segment = len(segments)
    first_segment = True
    for elem in row.iterchildren():
        if elem.tag == "milestone":
            # We check first if we are continuing
            if elem.attrib.get("continued", "false").lower() == "true":
                segment = template[-1]
                segment.scan += "/"
                segment.more_than_a_line = True
            else:
                segment = Segment(start_a_line=first_segment, scan="/" if first_segment else "")
                template.append(segment)
            if first_segment:
                first_segment = False
        elif elem.tag == "word":
            segment.scan += elem.attrib["sy"]

if _check:
    lines = 0
    for row in template:
        print(row)
        lines += row.scan.count("/")
print(lines)

uniques = {element.scan: [] for element in template}
print(uniques)
print(len(uniques))
xml_virgil = et.parse("data/generated-compact/virgil-compact.xml")
for scan in uniques:
    for poem in xml_virgil.xpath("./div/div"):
        # For full line, it's simple, we get the line scan and check a match with our current one
        if scan[0] == "/" and scan.count("/") == 1 and "1" in scan and "6" in scan:
            for line in poem.xpath("./line"):
                line_scan = _line_scan(line)
                if line_scan == scan:
                    uniques[scan].append([
                        "<line>",
                        f"""<milestone source="{line.attrib["n"]}" />""",
                        *_line_to_string(line),
                        "</line>"
                    ])
        # For double line, still simple: we first check if a line match the first of our line (.startswith)
        #   and then we check the second one
        elif scan[0] == "/" and scan.count("/") == 2 and scan.count("1A") == 2 and scan.count("6A") == 2:
            lines = poem.xpath("./line")
            lid = 0
            while lid < len(lines):
                line = lines[lid]
                line_scan = _line_scan(line)
                if scan.startswith(line_scan) and lid < len(lines) -1:
                    next_line_scan = _line_scan(lines[lid+1])
                    if line_scan + next_line_scan == scan:
                        uniques[scan].append([
                            "<line>",
                            f"""<milestone source="{line.attrib["n"]}" />""",
                            *_line_to_string(line),
                            "</line>",
                            "<line>",
                            f"""<milestone source="{lines[lid+1].attrib["n"]}" />""",
                            *_line_to_string(lines[lid+1]),
                            "</line>",
                        ])
                lid += 1
        # We single out the case of line starts: we get the full line scan to filter them out based on a startwith
        #   Then we progressively scan until it starts with the right start
        #   And just in case, we match completely the same scan (because a word can go hover a D/S split).
        elif scan.startswith("/") and scan.count("/") == 1: # Single line start
            for line in poem.xpath("./line"):
                line_scan = _line_scan(line)
                if line_scan.startswith(scan):
                    temp_scan = "/"
                    words = []
                    for elem in line.xpath("./word"):
                        temp_scan += elem.attrib["sy"]
                        words.append(elem)
                        if temp_scan.startswith(scan): # We stop when one contains the other
                            break
                    if temp_scan == scan: # We check that it's a strict equality
                        uniques[scan].append([
                            "<line>",
                            f"""<milestone source="{line.attrib["n"]}" />""",
                            *[et.tostring(word, encoding=str).strip() for word in words],
                        ])
        # Reverse of the first one
        elif not scan.startswith("/") and scan.count("/") == 0: # Single line end
            for line in poem.xpath("./line"):
                if words := _tail_scan_matching(line, scan):
                    uniques[scan].append([
                        f"""<milestone source="{line.attrib["n"]}" />""",
                        *[et.tostring(word, encoding=str).strip() for word in words],
                        "</line>"
                    ])
        # We got the full line followeg by a bit
        elif scan.startswith("/") and scan.count("/") == 2: # Single line start
            lines = poem.xpath("./line")
            lid = 0
            while lid < len(lines)-1:
                line = lines[lid]
                line_scan = _line_scan(line)
                # If our first line matches, we go into the second line
                if scan.startswith(line_scan):
                    next_line_scan = _line_scan(lines[lid+1])
                    # Now we match if the two lines starts with the pattern with search
                    if (line_scan+next_line_scan).startswith(scan):
                        temp_scan = line_scan+"/" # We start with the second one already
                        words = []
                        for elem in lines[lid+1].xpath("./word"):
                            temp_scan += elem.attrib["sy"]
                            words.append(elem)
                            if temp_scan.startswith(scan): # We stop when one contains the other
                                break
                        if temp_scan == scan: # We check that it's a strict equality
                            uniques[scan].append([
                                "<line>",
                                f"""<milestone source="{line.attrib["n"]}" />""",
                                *_line_to_string(line),
                                "</line>",
                                "<line>",
                                f"""<milestone source="{lines[lid+1].attrib["n"]}" />""",
                                *[et.tostring(word, encoding=str).strip() for word in words],
                            ])
                lid += 1
        elif not scan.startswith("/") and scan.count("/") == 1:
            lines = poem.xpath("./line")
            lid = 0
            while lid < len(lines)-1: # We stop earlier because we need two consecutive lines
                line = lines[lid]
                first_segment, second_segment = scan.split("/")
                second_segment = "/"+second_segment
                if words := _tail_scan_matching(line, first_segment): # We match the first element
                    next_line_scan = _line_scan(lines[lid+1])
                    if "6" in second_segment: # We got a full line for the second part
                        if next_line_scan == second_segment: # We got a full line as second segment, let's go
                            uniques[scan].append([
                                f"""<milestone source="{line.attrib["n"]}" />""",
                                *[et.tostring(word, encoding=str).strip() for word in words],
                                "</line>",
                                "<line>",
                                f"""<milestone source="{lines[lid + 1].attrib["n"]}" />""",
                                *_line_to_string(line),
                                "</line>"
                            ])
                    elif next_line_scan.startswith(second_segment):
                        temp_scan = "/"
                        words_seg_2 = []
                        for elem in lines[lid+1].xpath("./word"):
                            temp_scan += elem.attrib["sy"]
                            words_seg_2.append(elem)
                            if temp_scan.startswith(next_line_scan):  # We stop when one contains the other
                                break
                        if temp_scan == next_line_scan:  # We check that it's a strict equality
                            uniques[scan].append([
                                f"""<milestone source="{line.attrib["n"]}" />""",
                                *[et.tostring(word, encoding=str).strip() for word in words],
                                "</line>",
                                "<line>",
                                f"""<milestone source="{lines[lid+1].attrib["n"]}" />""",
                                *[et.tostring(word, encoding=str).strip() for word in words_seg_2],
                            ])

                lid += 1
        # Two missing approaches:
        #   - end of line + beginning of line
        #   - end of line + full line

# for scan, pool in uniques.items():
#     nocc = len([row for row in template if row.scan == scan])
#     print(f"{scan}: {len(pool)} candidates for {nocc} occurrences in the cento")


uniques = {
    scan: list(map(tuple, values))
    for scan, values in uniques.items()
}

rows = []
for scan, pool in uniques.items():
    nocc = len([row for row in template if row.scan == scan])
    rows.append([scan, len(pool), nocc])
rows.sort(key=lambda r: r[1], reverse=True)
print(tabulate(rows, headers=["Scan", "Candidates", "Occurrences in Cento"], tablefmt="github"))


def make_cento(file: int, seed: int = 42, max_candidates: int = 100):
    random.seed(seed)
    xml = []
    attempts = Counter()
    for segment in template:
        candidates = uniques[segment.scan]
        if not segment.start_a_line and "6A" not in xml[-1]: # We only need to check new merge
            last_word = _w_to_xml(xml[-1])
            last_word_strip = strip_punct(last_word)
            nb_candidates = max_candidates
            validated_candidate = None
            former_candidates = set()
            situation = ""
            while nb_candidates > 0:
                candidate = random.choice(sorted(list(set(candidates) | former_candidates)))
                # If it's not starting, the first word is the second element (first is milestone)
                candidate_first_word = _w_to_xml(candidate[1])
                candidate_first_word_strip = strip_punct(candidate_first_word)
                # First case: last word is ending with a SY, we check if next one starts with VOWEL
                if last_word.attrib.get("mf", "") == "SY":
                    situation = "Elision removed"
                    attempts[situation] += 1
                    if _elision(last_word_strip, candidate_first_word_strip).word1_elided:
                        validated_candidate = candidate
                        break
                # We check that if last word ends with a short, it does not turn into a long
                elif last_word.attrib["sy"].endswith("c"):
                    situation = "Short lengthened"
                    attempts[situation] += 1
                    # Two not in a VOWEL means two consonnants, which means turned into long
                    if strip_punct(last_word)[-1] not in _VOWELS and strip_punct(candidate_first_word)[0] not in _VOWELS:
                        continue
                    else:
                        validated_candidate = candidate
                        break
                else:
                    # We only check is something becomes elided
                    # A new elision should not happen on a single char word
                    if len(strip_punct(last_word)) == 1:
                        validated_candidate = candidate
                        break
                    if not bool(_elision(last_word_strip, candidate_first_word_strip)):
                        validated_candidate = candidate
                        break
                    else:
                        situation = "Elision added"
                        attempts["Elision added"] += 1
                nb_candidates -= 1
                former_candidates.add(candidate)
            if validated_candidate:
                xml.append("<custom_join />")
                xml.extend(validated_candidate)
            elif _check:
                print("Previous", xml[-1])
                for candidate in former_candidates:
                    print("\t"+" ".join(candidate))
                error = NotFoundCandidate(f"({situation}) Not a single candidate found in 30 attempts")
                error.situation = situation
                raise error
        else:
            candidate = random.choice(candidates)
            xml.extend(candidate)
    xml = et.fromstring(f"<poem>{'\n'.join(xml)}</poem>")

    with open(f"data/generated-compact/exact/cento_{file:04d}.xml", "w") as f:
        f.write(et.tostring(xml, pretty_print=True, encoding=str))

    return attempts

file = 0
seed = 0
errors = []

pbar = tqdm.tqdm(desc="")
while file < 1000:
    try:
        make_cento(file, seed=42 + seed)
        file += 1
    except NotFoundCandidate as E:
        errors.append(E.situation)
    seed += 1
    pbar.set_postfix(successes=file, attempts=seed)
    pbar.update(1)

pbar.close()