# Stylometry Project: Ausonius Cento Nuptialis

## Overview

This project analyses the stylistic affinities of Ausonius's *Cento Nuptialis*
against:
1. A LamdaG model of Ausonius (built from his other hexameter works)
2. Vergil (as a comparison author)

The method follows the pipeline used in the **Liber-Regum** project
(`Liber-Regum/Lexical analysis/`).

## Project Structure

```
cento/stylometry/
├── raw/                         # Source files (fixtures)
│   ├── ausonius/                # Pedecerto XML (17 hexameter works, no cento)
│   ├── question/                # Pedecerto XML (cento_nuptialis.xml)
│   ├── vergil/                  # Hypotactic JSON (Georgics 1-4)
│   ├── aeneid/                  # Hypotactic JSON (Aeneid 1-12)
│   └── background/              # Ovid, Lucan, Silius, Valerius Flaccus
├── processed/                   # Intermediate files (reproducible)
│   ├── ausonius_hexameter/      # Clean hexameter XML (from extract_hexameter.py)
│   ├── question_hexameter/      # Clean hexameter XML for cento
│   ├── ausonius/                # Plain text (from extract_text.py)
│   ├── vergil/                  # Plain text (from extract_text.py)
│   ├── aeneid/                  # Plain text (from extract_text.py)
│   ├── background/              # Plain text (from extract_text.py)
│   ├── question/                # Plain text (from extract_text.py)
│   └── udpipe_cache/            # Shared UDPipe cache
├── lexical_model/               # Lexical analysis corpora (latin-masking output)
│   ├── ausonius/                # *_sentences.quesplit.masked.txt
│   ├── vergil/                  # Vergil Georgics
│   ├── aeneid/                  # Vergil Aeneid
│   ├── background/
│   └── question/                # cento_nuptialis
├── metrical_model/              # Metrical numbered output
│   ├── ausonius/                # *_sentences.metrical.txt
│   ├── vergil/
│   ├── aeneid/
│   ├── background/
│   └── question/
├── scripts/                     # Pipeline scripts
│   ├── xml_utils.py             # Shared XML utilities (clean_xml)
│   ├── metrical_numbering.py    # Pedecerto XML → prime-encoded numbers
│   ├── hypotactic_numbering.py  # Hypotactic JSON → prime-encoded numbers
│   ├── sentence_mapping.py      # Sentence↔XML alignment (FIFO permutation)
│   ├── extract_hexameter.py     # Principled hexameter extraction (≥10 lines)
│   ├── extract_text.py          # XML/JSON → plain text (one line per verse)
│   ├── generate_metrical.py     # Produce metrical/ numbered output
│   ├── extract_hypotactic.py    # Author JSON → individual book JSONs
│   ├── download_ausonius.py     # Pedecerto download
│   ├── process.py               # Latin-masking pipeline wrapper
│   ├── corpus_utils.py          # Hypotactic data utilities
│   ├── naming.py                # Naming conventions
│   └── analyze_hexameter.py     # Hexameter analysis (diagnostic)
├── tests/                       # Test files
│   ├── test_metrical_numbering.py
│   └── test_extract_hexameter.py
├── common_adverbs.txt           # Latin-masking adverb list
├── PLAN.md                      # Project overview
└── PIPELINE.md                  # Replicable runbook
```

## Data Sources

### Ausonius Works (Pedecerto)

Source: https://www.pedecerto.eu/pagine/autori/idautori/183

All 31 works by Ausonius have been downloaded as XML files into `raw/ausonius/`.
Selected hexameter works are extracted automatically by `scripts/extract_hexameter.py`
(finds continuous stretches ≥10 hexameter lines). Filtered XML goes to
`processed/ausonius_hexameter/`.

### Hypotactic Authors

Individual poem JSONs extracted from the hypotactic corpus using
`scripts/extract_hypotactic.py`. Each file contains hexameter lines only.

- **Vergil Georgics** (`raw/vergil/`): 4 books
- **Vergil Aeneid** (`raw/aeneid/`): 12 books
- **Background** (`raw/background/`): Ovid Metamorphoses (15 books),
  Lucan Bellum Civile (10 books), Silius Italicus Punica (17 books),
  Valerius Flaccus Argonautica (8 books)

### Download Instructions

```bash
cd cento/stylometry
~/venv/py314/bin/python scripts/download_ausonius.py
```

This downloads all 31 works by Ausonius as XML files into `raw/ausonius/`.

### Hexameter Extraction

`scripts/extract_hexameter.py` reads XML files from `raw/ausonius/` and
`raw/question/`, finds continuous stretches of 10+ hexameter lines, and
writes clean XML to `processed/ausonius_hexameter/` and
`processed/question_hexameter/`.

### Hexameter Works for LamdaG Model

17 works in `raw/ausonius/` (excluding cento_nuptialis):
caesares, commemoratio_professorum_burdigalensium, cupido_cruciatus, eclogae,
ephemeris, epigrammata, epistulae, genethliacos, griphus_ternarii_numeri,
mosella, oratio_consulis_ausonii_versibus_rhopalicis, ordo_urbium_nobilium,
pater_ad_filium, precationes_variae, protrepticus_ad_nepotem, technopaegnion,
uersus_paschales.

## Pipeline

See **PIPELINE.md** for full replicable instructions.

1. **Extract raw**: Download Ausonius XML + extract hypotactic JSONs → `raw/`
2. **Extract hexameter**: Find continuous hexameter stretches → `processed/ausonius_hexameter/`
3. **Extract text**: XML/JSON → one `.txt` per work → `processed/`
4. **Sentence split + mask**: latin-masking pipeline → `lexical_model/`
5. **Metrical numbering**: XML/JSON + sentences → numbered output → `metrical_model/`
6. **Analysis**: LamdaG authorship verification

## Next Steps

- [x] Download Ausonius XML from Pedecerto → `raw/ausonius/`
- [x] Extract hypotactic poems → `raw/vergil/`, `raw/background/`
- [x] Create metrical numbering modules (`metrical_numbering.py`, `hypotactic_numbering.py`)
- [x] Create sentence mapping module (`sentence_mapping.py`)
- [x] Restructure directories
- [x] Replace `to_process.md` with principled hexameter extraction
- [x] Cleanup: delete stale files, remove non-hexameter raw XMLs
- [x] Write `extract_text.py` and `generate_metrical.py`
- [x] Write `PIPELINE.md` runbook
- [x] Run latin-masking on all corpora → `lexical_model/`
- [x] Generate metrical output → `metrical_model/`
- [ ] Fix metrical/lexical token alignment (316 lines differ due to latin-masking word splits like `anne` → `an ne`)
- [ ] Build LamdaG model and evaluate
