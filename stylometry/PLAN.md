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
├── raw/                         # Source files (one-time data)
│   ├── ausonius/                # Pedecerto XML (one file per work)
│   ├── vergil/                  # Hypotactic JSON (one file per book)
│   └── background/              # Ovid, Lucan, Silius, Valerius Flaccus
├── processed/                   # Intermediate files (reproducible)
│   ├── ausonius/                # Filtered XML, text, sentences
│   ├── vergil/
│   ├── background/
│   └── question/                # cento_nuptialis
├── model/                       # Lexical analysis corpora
│   ├── ausonius/                # *_sentences.quesplit.masked.txt
│   ├── vergil/
│   ├── background/
│   └── question/
├── metrical/                    # Metrical numbered output
│   ├── ausonius/                # *_sentences.metrical.txt
│   ├── vergil/
│   ├── background/
│   └── question/
├── scripts/                     # Pipeline scripts
│   ├── metrical_numbering.py    # Pedecerto XML → numbers
│   ├── hypotactic_numbering.py  # Hypotactic JSON → numbers
│   ├── sentence_mapping.py      # Permutation mapping
│   ├── filter_hexameter.py      # XML hexameter filtering
│   ├── extract_sentences.py     # XML → text extraction
│   ├── extract_hypotactic.py    # Author JSON → individual poems
│   ├── download_ausonius.py     # Pedecerto download
│   ├── process.py               # Latin-masking pipeline wrapper
│   ├── corpus_utils.py          # Hypotactic data utilities
│   └── naming.py                # Naming conventions
├── tests/                       # Test files
│   └── test_metrical_numbering.py
├── common_adverbs.txt           # Latin-masking adverb list
└── PLAN.md                      # This file
```

## Data Sources

### Ausonius Works (Pedecerto)

Source: https://www.pedecerto.eu/pagine/autori/idautori/183

All 31 works by Ausonius have been downloaded as XML files into `raw/ausonius/`.
Selected hexameter works are listed in `to_process.md` (to be replaced by
automated extraction). Filtered XML goes to `processed/ausonius/`, text files
to `processed/ausonius/`, and masked files to `model/ausonius/`.

### Hypotactic Authors

Individual poem JSONs extracted from the hypotactic corpus into `raw/vergil/`
and `raw/background/` using `scripts/extract_hypotactic.py`. Each file
contains hexameter lines only.

- **Vergil**: Aeneid (12 books), Georgics (4 books)
- **Background**: Ovid Metamorphoses (15 books), Lucan Bellum Civile (10 books),
  Silius Italicus Punica (17 books), Valerius Flaccus Argonautica (8 books)

### Download Instructions

```bash
cd cento/stylometry
~/venv/py314/bin/python scripts/download_ausonius.py
```

This downloads all 31 works by Ausonius as XML files into `raw/ausonius/`.

### Meter Filtering

`scripts/filter_hexameter.py` reads `to_process.md` for the list of files to
process, extracts only hexameter lines, and skips lines with:
- Empty or "X" meter (unscanned)
- `pattern="not scanned"` attribute
- Asterisks in word text

Filtered XML goes to `processed/ausonius/`, text to `processed/ausonius/`.

### Hexameter Works for LamdaG Model

7 works selected in `to_process.md` (excluding cento_nuptialis):
mosella, cupido_cruciatus, ordo_urbium_nobilium, griphus_ternarii_numeri,
protrepticus_ad_nepotem, precationes_variae, genethliacos.

## Pipeline

1. **Extract raw**: Download Ausonius XML + extract hypotactic JSONs → `raw/`
2. **Filter hexameter**: XML → hexameter-only XML → `processed/ausonius/`
3. **Extract text**: XML → plain text files → `processed/`
4. **Sentence split + mask**: latin-masking pipeline → `model/`
5. **Metrical numbering**: XML/JSON + sentences → numbered output → `metrical/`
6. **Analysis**: LamdaG authorship verification

## Next Steps

- [x] Download Ausonius XML from Pedecerto → `raw/ausonius/`
- [x] Extract hypotactic poems → `raw/vergil/`, `raw/background/`
- [x] Create metrical numbering modules (`metrical_numbering.py`, `hypotactic_numbering.py`)
- [x] Create sentence mapping module (`sentence_mapping.py`)
- [x] Restructure directories
- [ ] Replace `to_process.md` with principled hexameter extraction
- [ ] Run latin-masking on Ausonius question text
- [ ] Generate metrical output for all corpora
- [ ] Build LamdaG model and evaluate
