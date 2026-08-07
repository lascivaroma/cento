# Pipeline Runbook

This document describes every step to reproduce the stylometry analysis from
scratch.  Each step runs a saved script — no inline Python.

## Prerequisites

```bash
# Python 3.14 virtualenv with latin_masking installed
source ~/venv/py314/bin/activate

# Working directory
cd ~/code/cento/stylometry
```

All scripts live in `scripts/` and are invoked from the project root.
`PYTHONPATH=scripts` is set where needed.

---

## Step 0 — Cleanup

```bash
~/venv/py314/bin/python3 scripts/clean.py
```

Removes all pipeline outputs from `processed/`, `lexical_model/`, and
`metrical_model/`, but preserves the UDPipe cache in `processed/udpipe_cache/`.

---

## Step 1 — Extract hexameter XML

Find continuous hexameter stretches ≥10 lines in raw XML files.

```bash
PYTHONPATH=scripts python scripts/extract_hexameter.py
```

- **Input**: `raw/ausonius/*.xml` (17 files), `raw/question/*.xml` (1 file)
- **Output**: `processed/ausonius_hexameter/*.xml`, `processed/question_hexameter/*.xml`

---

## Step 2 — Extract plain text

Convert source files to one `.txt` per work (one verse per line).

```bash
PYTHONPATH=scripts python scripts/extract_text.py
```

- **Input**:
  - `processed/ausonius_hexameter/*.xml` → `processed/ausonius/*.txt`
  - `processed/question_hexameter/*.xml` → `processed/question/*.txt`
  - `raw/vergil/*.json` → `processed/vergil/*.txt`
  - `raw/aeneid/*.json` → `processed/aeneid/*.txt`
  - `raw/background/*.json` → `processed/background/*.txt`

---

## Step 3 — Sentence splitting + masking (latin-masking)

Run the latin-masking pipeline on each corpus.  Stage 1 splits sentences
and extracts adverbs; stage 2 masks content words with POS tags.
All output goes into `processed/`.

```bash
# Ausonius (generates common_adverbs.txt)
python scripts/process.py --stage1 --stage2 --keep-adverbs \
    --output-dir processed/ausonius processed/ausonius/*.txt

# Vergil Georgics
python scripts/process.py --stage1 --stage2 --keep-adverbs \
    --output-dir processed/vergil processed/vergil/*.txt

# Vergil Aeneid
python scripts/process.py --stage1 --stage2 --keep-adverbs \
    --output-dir processed/aeneid processed/aeneid/*.txt

# Background
python scripts/process.py --stage1 --stage2 --keep-adverbs \
    --output-dir processed/background processed/background/*.txt

# Question (cento)
python scripts/process.py --stage1 --stage2 --keep-adverbs \
    --output-dir processed/question processed/question/*.txt
```

---

## Step 4 — Copy masked files to lexical_model/

Only the `*_sentences.quesplit.masked.txt` files go into `lexical_model/`.

```bash
for corpus in ausonius vergil aeneid background question; do
    mkdir -p lexical_model/$corpus
    cp processed/$corpus/*_sentences.quesplit.masked.txt lexical_model/$corpus/
done
```

- **Output**:
  - `lexical_model/{ausonius,vergil,aeneid,background,question}/*_sentences.quesplit.masked.txt`

These are the **lexical analysis corpora** for LamdaG.

---

## Step 5 — Metrical numbering

Align sentence boundaries with metrical position numbers from the source
scansion data.  Each word is replaced by its prime-encoded integer
(L=2, S=3, E=5, PE=7, Q=11).

```bash
PYTHONPATH=scripts python scripts/generate_metrical.py
```

- **Input**: Source files + `*_sentences.txt` from `processed/`
- **Output**: `metrical_model/{ausonius,vergil,aeneid,background,question}/*_sentences.metrical.txt`

---

## Step 6 — Line-based metrical numbering

Generate one sentence per hexameter line, with each word replaced by its
prime-encoded metrical position number.  Unlike Step 5, no sentence splitting
is used — each hexameter line is its own sentence.  Every sentence ends with
`<EOL>`.

```bash
PYTHONPATH=scripts python scripts/generate_metrical_lines.py
```

- **Input**: Source XML/JSON files (same as Step 5)
- **Output**: `metrical_model_lines/{ausonius,vergil,aeneid,background,question}/*.mapped_lines.txt`

---

## Step 7 — Analysis

LambdaG models are built and evaluated in the Jupyter notebooks:

- `cento_stylometry.ipynb` — lexical (POS-masked) analysis
- `cento_metrical_stylometry.ipynb` — sentence-based metrical analysis
- `cento_metrical_lines_stylometry.ipynb` — line-based metrical analysis (N=1,2,4)
- `cento_syntactic_stylometry.ipynb` — syntactic analysis
- `cento_sentence_similarity.ipynb` — per-sentence similarity visualization

---

## Step 8 — Generated cento conversion

Convert automatically generated centos to all stylometry formats.  Uses
`la_senter` for sentence splitting and `latin_masking.clitics` for que-splitting
(no UDPipe).  POS masking uses Pedecerto POS tags with a manually editable
mapping file.

```bash
# Process a single cento for testing (exact)
PYTHONPATH=scripts python scripts/generate_generated.py --source-dir ../data/generated-compact/exact --limit 1

# Process all 1000 exact centos
PYTHONPATH=scripts python scripts/generate_generated.py --source-dir ../data/generated-compact/exact

# Process loose centos
PYTHONPATH=scripts python scripts/generate_generated.py --source-dir ../data/generated-compact/loose
```

- **Input**: Source directory containing `cento_*.xml` files
- **Mapping**: `pos_mapping.tsv` (Pedecerto POS → UD POS, editable)
- **Output tag**: Derived from the source directory name (e.g. `exact` → `generated_exact`, `loose` → `generated_loose`)
- **Output**:
  - `processed/generated_{tag}/*.txt` — plain text with pipe markers
  - `processed/generated_{tag}/*_sentences.txt` — sentence-split
  - `processed/generated_{tag}/*_sentences.quesplit.txt` — que-split
  - `processed/generated_{tag}/*_sentences.quesplit.masked.txt` — POS-masked
  - `lexical_model/generated_{tag}/*_sentences.quesplit.masked.txt` — copy
  - `metrical_model/generated_{tag}/*_sentences.metrical.txt` — sentence-based metrical
  - `metrical_model_lines/generated_{tag}/*.mapped_lines.txt` — line-based metrical

---

## Reproducing from scratch

```bash
cd ~/code/cento/stylometry
source ~/venv/py314/bin/activate

# Step 0
~/venv/py314/bin/python3 scripts/clean.py

# Step 1
PYTHONPATH=scripts python scripts/extract_hexameter.py

# Step 2
PYTHONPATH=scripts python scripts/extract_text.py

# Step 3
for corpus in ausonius vergil aeneid background question; do
    python scripts/process.py --stage1 --stage2 --keep-adverbs \
        --output-dir processed/$corpus processed/$corpus/*.txt
done

# Step 4
for corpus in ausonius vergil aeneid background question; do
    mkdir -p lexical_model/$corpus
    cp processed/$corpus/*_sentences.quesplit.masked.txt lexical_model/$corpus/
done

# Step 5
PYTHONPATH=scripts python scripts/generate_metrical.py
```
