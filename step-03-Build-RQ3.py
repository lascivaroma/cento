import random
import re
import tqdm
import lxml.etree as et

from dataclasses import dataclass
from typing import List, Counter
from functools import lru_cache
from pycento.elision import check_elision, ElisionResult
from pycento.scan_simplifiyer import simplify_scan
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
    def loose_scan(self):
        return _scan_to_loose_scan(self.scan)


    @property
    def length(self):
        # ToDo for loose
        return "int"


@lru_cache(maxsize=None)
def _is_hypermetric(line):
    scan = _line_scan(line)
    return "7" in scan or scan.count("6") > 2


def strip_punct(word_tag):
    return re.sub(r"\W", "", word_tag.text)

@lru_cache(maxsize=None)
def letters_to_ux(word1, word2):
    return re.sub(
        r"[a-z]", "u",
        re.sub(
            r"[A-Z]", "-",
            re.sub(r"\d+", "", word1.attrib["sy"]+word1.attrib["sy"])
        )
    )

_SCANEQUIV = {
    "d": "1",
    "s": "2",
    "D": "4",
    "S": "4",
    "X": "2",
    "/": "/"
}

@lru_cache(maxsize=None)
def _scan_to_loose_scan(scan) -> str:
    """

    >>> _scan_to_loose_scan("/5A5b5c6A6X")
    '/44'
    >>> _scan_to_loose_scan("/1A1b1c2A2T3A3b3c4A")
    '/4442'
    """
    scan = simplify_scan("/".join(
        [
            simplify_scan(scan_part)
            for scan_part in scan.split("/")
        ]
    ))
    return "".join([_SCANEQUIV[letter] for letter in scan])
    return Scansion().first_word_elided(sequence)

@lru_cache(maxsize=None)
def _check_loose_sum(scan1, scan2) -> str:
    return sum(list(map(int, scan1.replace("/", "")))) >= sum(list(map(int, scan2.replace("/", ""))))

@lru_cache(maxsize=None)
def _elision(w1: str, w2: str) -> ElisionResult:
    return check_elision(w1, w2)
    return Scansion().first_word_elided(sequence)

class NotFoundCandidate(ValueError):
    pass

@lru_cache(maxsize=None)
def _tail_scan_matching(line, scan):
    temp_scan = ""
    words = []
    for elem in line.xpath("./word")[::-1]:
        temp_scan = elem.attrib["sy"] + temp_scan

        words.append(elem)
        if _scan_to_loose_scan(temp_scan) == scan:  # stop once one contains the other
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
        lines += row.scan.count("/")
        print(lines+1, row, row.loose_scan)

run_template = True
if run_template:
    uniques = {element.loose_scan: [] for element in template}
    print(uniques)
    print(len(uniques))
    xml_virgil = et.parse("data/generated-compact/virgil-compact.xml")
    for scan in uniques:
        for poem in xml_virgil.xpath("./div/div"):
            # For full line, it's simple, we get the line scan and check a match with our current one
            if scan == "/444444":
                for line in poem.xpath("./line[@pattern!='not scanned']"):
                    if _is_hypermetric(line):
                        continue
                    uniques[scan].append([
                        "<line>",
                        f"""<milestone source="{line.attrib["n"]}" />""",
                        *_line_to_string(line),
                        "</line>"
                    ])
            # For double line, still simple: we first check if a line match the first of our line (.startswith)
            #   and then we check the second one
            elif scan == "/444444/444444":
                lines = poem.xpath("./line")
                lid = 0
                while lid < len(lines) - 1:
                    line = lines[lid]
                    if (
                            line.attrib.get("pattern") == "not scanned"
                            or lines[lid+1].attrib.get("pattern") == "not scanned"
                    ):
                        lid += 1
                        continue
                    if _is_hypermetric(line) or _is_hypermetric(lines[lid+1]):
                        lid += 1
                        continue
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
                for line in poem.xpath("./line[@pattern!='not scanned']"):
                    # Unlike RQ2, we do not need to prescan the line
                    temp_scan = "/"
                    words = []
                    next_line_words = line.xpath("./word")
                    wid = 0
                    while wid < len(next_line_words):
                        elem = next_line_words[wid]
                        temp_scan += elem.attrib["sy"]
                        words.append(elem)
                        if _scan_to_loose_scan(temp_scan) == scan:
                            # EXCEPT if the next word is prodelided ! Then we go a little further
                            if wid < len(next_line_words)-1 and next_line_words[wid + 1].attrib.get("sy") == "PE":
                                words.append(next_line_words[wid + 1])
                            break
                        wid += 1
                    if _scan_to_loose_scan(temp_scan) == scan: # We check that it's a strict equality
                        uniques[scan].append([
                            "<line>",
                            f"""<milestone source="{line.attrib["n"]}" />""",
                            *[et.tostring(word, encoding=str).strip() for word in words],
                        ])
            # Reverse of the first one
            elif not scan.startswith("/") and scan.count("/") == 0: # Single line end
                for line in poem.xpath("./line[@pattern!='not scanned']"):
                    if _is_hypermetric(line):
                        continue
                    if words := _tail_scan_matching(line, scan):
                        uniques[scan].append([
                            f"""<milestone source="{line.attrib["n"]}" />""",
                            *[et.tostring(word, encoding=str).strip() for word in words],
                            "</line>"
                        ])
            # We got the full line followed by a bit
            elif scan.startswith("/") and scan.count("/") == 2:
                scan_bit = "/"+scan.split("/")[-1]
                lid = 0
                lines = poem.xpath("./line")
                while lid < len(lines) - 1:
                    line = lines[lid]
                    if line.attrib.get("pattern") == "not scanned":
                        lid += 1
                        continue
                    if _is_hypermetric(lines[lid-1]):
                        lid += 1
                        continue
                    # Unlike RQ2, we do not need to prescan the line
                    temp_scan = "/"
                    words = []
                    line_words = line.xpath("./word")
                    wid = 0
                    while wid < len(line_words):
                        elem = line_words[wid]
                        try:
                            temp_scan += elem.attrib["sy"]
                        except Exception:
                            print(et.tostring(line, encoding=str).strip())
                        words.append(elem)
                        if _scan_to_loose_scan(temp_scan) == scan_bit:
                            # EXCEPT if the next word is prodelided ! Then we go a little further
                            if wid < len(line_words)-1 and line_words[wid + 1].attrib.get("sy") == "PE":
                                words.append(line_words[wid + 1])
                            break
                        wid += 1
                    if _scan_to_loose_scan(temp_scan) == scan_bit: # We check that it's a strict equality
                        if lid < 1 or lines[lid-1].attrib.get("pattern") == "not scanned":
                            lid += 1
                            continue

                        uniques[scan].append([
                            "<line>",
                            f"""<milestone source="{lines[lid-1].attrib["n"]}" />""",
                            *_line_to_string(lines[lid-1]),
                            "</line>",
                            "<line>",
                            f"""<milestone source="{line.attrib["n"]}" />""",
                            *[et.tostring(word, encoding=str).strip() for word in words],
                        ])
                    lid += 1
            # Ending bit followed by starting bit at least (potential full line after ending bit)
            elif not scan.startswith("/") and scan.count("/") == 1:
                lines = poem.xpath("./line")
                lid = 0
                while lid < len(lines)-1: # We stop earlier because we need two consecutive lines
                    line = lines[lid]
                    if line.attrib.get("pattern") == "not scanned" or lines[lid+1].attrib.get("pattern") == "not scanned":
                        lid += 1
                        continue
                    if _is_hypermetric(line):
                        lid += 1
                        continue
                    first_segment, second_segment = [x for x in scan.split("/") if x]
                    second_segment = "/"+second_segment
                    if words := _tail_scan_matching(line, first_segment): # We match the first element
                        if second_segment == "/444444": # We got a full line for the second part
                            if _is_hypermetric(lines[lid+1]):
                                lid += 1
                                continue
                            uniques[scan].append([
                                f"""<milestone source="{line.attrib["n"]}" />""",
                                *[et.tostring(word, encoding=str).strip() for word in words],
                                "</line>",
                                "<line>",
                                f"""<milestone source="{lines[lid + 1].attrib["n"]}" />""",
                                *_line_to_string(lines[lid + 1]),
                                "</line>"
                            ])
                        else:
                            temp_scan = "/"
                            words_seg_2 = []
                            second_line_words = lines[lid+1].xpath("./word")
                            wid = 0
                            while wid < len(second_line_words):
                                elem = second_line_words[wid]
                                temp_scan += elem.attrib["sy"]
                                words_seg_2.append(elem)
                                if _scan_to_loose_scan(temp_scan) == second_segment:  # We stop when one contains the other
                                    if wid < len(second_line_words)-1 and second_line_words[wid+1].attrib.get("sy") == "PE":
                                        words.append(second_line_words[wid+1])
                                        print("PRODELISION INCLUDED !")
                                    break
                                wid += 1
                            if _scan_to_loose_scan(temp_scan) == second_segment:  # We check that it's a strict equality
                                uniques[scan].append([
                                    f"""<milestone source="{line.attrib["n"]}" />""",
                                    *[et.tostring(word, encoding=str).strip() for word in words],
                                    "</line>",
                                    "<line>",
                                    f"""<milestone source="{lines[lid+1].attrib["n"]}" />""",
                                    *[et.tostring(word, encoding=str).strip() for word in words_seg_2],
                                ])

                    lid += 1
            else:
                print(f"Missing for {scan}")
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
        nocc = len([row for row in template if row.loose_scan == scan])
        rows.append([scan, len(pool), nocc])
    rows.sort(key=lambda r: r[1], reverse=True)
    print(tabulate(rows, headers=["Scan", "Candidates", "Occurrences in Cento"], tablefmt="github"))

run_cento = True
if run_cento:
    def make_cento(file: int, seed: int = 42, max_candidates: int = 100):
        random.seed(seed)
        xml = []
        attempts = Counter()
        for segment in template:
            candidates = uniques[segment.loose_scan]
            if not segment.start_a_line and "6" not in segment.scan: # We only need to check new merge
                # if "".join(xml).count("<line") == 43:
                #     print("".join(xml).count("<line"), segment)
                #     print(xml)
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
                    # First situation: we had a prodelision, it should not affect the metric
                    if last_word.attrib.get("mf", "") == "PE":
                        print("PRODELISION VALIDATION")
                        validated_candidate = candidate
                        break
                    # Second case: last word is ending with a SY, we check if next one starts with VOWEL
                    elif last_word.attrib.get("mf", "") == "SY":
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
                        elif bool(_elision(last_word_strip, candidate_first_word_strip)):
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
                # if "".join(xml).count("<line") == 43:
                #     print(segment, segment.loose_scan, candidate)
                #     raise Exception
                #     break
        xml = et.fromstring(f"<poem>{'\n'.join(xml)}</poem>")
        for lid, line in enumerate(xml.xpath("//line")):
            line.attrib["n"] = str(lid+1)
        with open(f"data/generated-compact/loose/cento_{file:04d}.xml", "w") as f:
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