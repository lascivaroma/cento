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
├── ausonius_raw/              # Raw XML downloads from Pedecerto
├── download_ausonius.py       # Script to download Ausonius hexameter XML
├── preprocess.py              # Convert XML → sentences → masked (TBD)
├── build_model.py             # Build LamdaG model from Ausonius works (TBD)
├── evaluate.py                # Evaluate cento against model and Vergil (TBD)
└── PLAN.md                    # This file
```

## Data Sources

### Ausonius Works (Pedecerto)

Source: https://www.pedecerto.eu/pagine/autori/idautori/183

All 31 works by Ausonius have been downloaded as XML files into `ausonius_raw/`.
Some works contain a mix of meters; the `meter` attribute on each `<line>` element
indicates the meter type, where `H` = hexameter.

Meter distribution across downloaded files:

| File | H (hex) | Other meters | Notes |
|------|---------|-------------|-------|
| `mosella.xml` | 484 | 1 (X) | Almost pure hexameter |
| `uersus_paschales.xml` | 31 | 1 (X) | Almost pure hexameter |
| `cupido_cruciatus.xml` | 103 | 5 (", X) | Predominantly hexameter |
| `epitaphia_heroum.xml` | 66 | 80 (", P, X) | Mixed |
| `epigrammata.xml` | 294 | 178 (", G, G1, P, T, V, X) | Mixed |
| `epistulae.xml` | 521 | 755 (", D, F, G, G1, P, V, X) | Mixed |
| `technopaegnion.xml` | 163 | 34 (", X) | Predominantly hexameter |
| `parentalia.xml` | 191 | 278 (G, G1, P, V, X, Y) | Mixed |
| `praefationes.xml` | 41 | 49 (", F, P, X) | Mixed |
| `caesares.xml` | 91 | 148 (", P, X) | Mixed |
| `cento_nuptialis.xml` | 132 | 48 (", G, X) | **Target text** |
| `ephemeris.xml` | 133 | 110 (A, G, P, S1, X) | Mixed |
| `eclogae.xml` | 350 | 79 (", P, T, X) | Predominantly hexameter |
| `commemoratio_professorum_burdigalensium.xml` | 131 | 473 (", A, G, G1, P, S1, T, V, X, Y) | Mixed |
| `ordo_urbium_nobilium.xml` | 168 | 30 (", X) | Predominantly hexameter |
| `griphus_ternarii_numeri.xml` | 90 | 6 (", X) | Predominantly hexameter |
| `protrepticus_ad_nepotem.xml` | 100 | 7 (", X) | Predominantly hexameter |
| `epicedion_in_patrem.xml` | 32 | 37 (", P, X) | Mixed |
| `pater_ad_filium.xml` | 22 | 3 (", X) | Predominantly hexameter |
| `bissula.xml` | 18 | 31 (O, P, T, V, X) | Mixed |
| `periochae_iliados.xml` | 43 | 76 (", X) | Mixed |
| `periochae_odyssiae.xml` | 25 | 73 (", X) | Mixed |
| `fasti.xml` | 13 | 29 (", P, X) | Mixed |
| `genethliacos.xml` | 29 | 2 (", X) | Predominantly hexameter |
| `ad_patrem_de_suscepto_filio.xml` | 20 | 20 (P) | Mixed |
| `de_herediolo.xml` | 15 | 20 (", P, X) | Mixed |
| `ludus_septem_sapientium.xml` | 9 | 210 (", G, P, X) | Not hexameter |
| `precationes_variae.xml` | 85 | 4 (", X) | Predominantly hexameter |
| `oratio_consulis_ausonii_versibus_rhopalicis.xml` | 42 | 1 (X) | Almost pure hexameter |
| `appendix_ausoniana.xml` | 1 | 2 (V) | Not hexameter |
| `appendix_ausoniana_2.xml` | 34 | 122 (", D, F, G, G1, P, T, V, X, Y) | Mixed |

### Download Instructions

```bash
cd cento/stylometry
python download_ausonius.py
```

This downloads all 31 works by Ausonius as XML files into `ausonius_raw/`.

### Meter Filtering

A script (`filter_hexameter.py`) extracts only hexameter lines (`meter="H"`)
from files that contain a mix of meters. Files with no hexameter lines at all
are skipped.

Results: 29 files kept, 2 files skipped (`appendix_ausoniana.xml` and
`periochae_iliados.xml` have no hexameter lines).

### Hexameter Works for LamdaG Model

The following works have hexameter lines and are suitable for building the
Ausonius LamdaG model (excluding `cento_nuptialis` which is the target text):

| File | H lines | Total lines |
|------|---------|-------------|
| `epistulae.xml` | 245 | 672 |
| `epigrammata.xml` | 4 | 9 |
| `mosella.xml` | 484 | 485 |
| `parentalia.xml` | 191 | 469 |
| `praefationes.xml` | 33 | 89 |
| `ephemeris.xml` | 85 | 132 |
| `eclogae.xml` | 12 | 13 |
| `caesares.xml` | 91 | 197 |
| `technopaegnion.xml` | 163 | 195 |
| `ordo_urbium_nobilium.xml` | 168 | 196 |
| `commemoratio_professorum_burdigalensium.xml` | 131 | 610 |
| `griphus_ternarii_numeri.xml` | 90 | 96 |
| `protrepticus_ad_nepotem.xml` | 100 | 107 |
| `epitaphia_heroum.xml` | 66 | 173 |
| `precationes_variae.xml` | 17 | 17 |
| `oratio_consulis_ausonii_versibus_rhopalicis.xml` | 42 | 43 |
| `pater_ad_filium.xml` | 22 | 24 |
| `epicedion_in_patrem.xml` | 32 | 70 |
| `cupido_cruciatus.xml` | 103 | 109 |
| `genethliacos.xml` | 29 | 31 |
| `bissula.xml` | 18 | 48 |
| `periochae_odyssiae.xml` | 2 | 5 |
| `ad_patrem_de_suscepto_filio.xml` | 20 | 40 |
| `de_herediolo.xml` | 15 | 35 |
| `ludus_septem_sapientium.xml` | 9 | 251 |
| `fasti.xml` | 13 | 33 |
| `appendix_ausoniana_2.xml` | 1 | 13 |

**Total hexameter lines (excluding cento_nuptialis): ~1,980**

### File Classification (from `analyze_hexameter.py`)

The analysis script categorizes files based on hexameter content and continuous stretches:

| Category | Count | Files |
|----------|-------|-------|
| **pure_hexameter** | 1 | `precationes_variae.xml` (17/17 H) |
| **predominant_hexameter** | 13 | `mosella`, `uersus_paschales`, `technopaegnion`, `ordo_urbium_nobilium`, `oratio_consulis_ausonii_versibus_rhopalicis`, `protrepticus_ad_nepotem`, `genethliacos`, `griphus_ternarii_numeri`, `ephemeris`, `eclogae`, `pater_ad_filium`, `cupido_cruciatus`, `cento_nuptialis` |
| **mixed_hexameter** | 12 | `epistulae`, `parentalia`, `praefationes`, `epitaphia_heroum`, `commemoratio_professorum_burdigalensium`, `caesares`, `epicedion_in_patrem`, `de_herediolo`, `bissula`, `epigrammata`, `fasti`, `periochae_odyssiae` |
| **elegiac_couplets** | 1 | `ad_patrem_de_suscepto_filio.xml` (alternating H/P) |
| **minimal_hexameter** | 2 | `appendix_ausoniana_2.xml`, `ludus_septem_sapientium.xml` |
| **no_hexameter** | 2 | `appendix_ausoniana.xml`, `periochae_iliados.xml` |

**Recommendation**: Files in `pure_hexameter` and `predominant_hexameter` categories
are the best candidates for the Ausonius hexameter corpus. Files in `mixed_hexameter`
and `elegiac_couplets` need manual review — their hexameter lines may be interspersed
with non-hexameter content that could introduce noise.

## Pipeline (following Liber-Regum)

The analysis pipeline mirrors `Liber-Regum/Lexical analysis/latin_masking_pipeline.ipynb`:

1. **XML → Sentences**: Extract sentences from Pedecerto XML (preserving punctuation)
2. **-que Splitting**: Split -que enclitics using `latin_masking split-que`
3. **Masking**: Two-pass POS + adverb masking using UDPipe (`latin-evalatin24-240520`)
4. **Feature Extraction**: Build n-gram frequency vectors (LamdaG model)
5. **Classification**: Compare cento against Ausonius model and Vergil

## Next Steps

- [x] Create download script for Ausonius works
- [x] Run download script to populate `ausonius_raw/` (all 31 works)
- [x] Analyze meter distribution in downloaded files
- [x] Create `analyze_hexameter.py` to report on hexameter content per file
- [x] Create `filter_hexameter.py` to extract hexameter lines (skip unscanned/asterisk/not-scanned pattern)
- [x] Fix XML cleaning — line-by-line division stripping
- [x] Create `to_process.md` with selected files for corpus
- [x] Run filter on 7 selected files → 1,054 hexameter lines
- [x] Create `extract_sentences.py` to convert XML → text (preserving punctuation)
- [x] Run extract → 7 text files, 1,054 lines, 6,527 words
- [x] Run latin-masking pipeline (Stage 1 + Stage 2)
- [x] Build LamdaG model from Ausonius hexameter works
- [x] Obtain Vergil hexameter texts (Aeneid, Georgics, Eclogues)
- [x] Evaluate cento against both models
