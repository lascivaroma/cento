*This repository needs some heavy clean up, but we promise you it's the right repository for https://inria.hal.science/hal-05881529*

```bib
@inproceedings{nagy:hal-05881529,
  TITLE = {{The (almost) invisible poet: How Vergilian is Ausonius' Cento Nuptialis?}},
  AUTHOR = {Nagy, Benjamin and Cl{\'e}rice, Thibault},
  URL = {https://inria.hal.science/hal-05881529},
  BOOKTITLE = {{CHR 2027 - 7th Computational Humanities Research}},
  ADDRESS = {Manchester (UK), United Kingdom},
  YEAR = {2027},
  MONTH = Jan,
  KEYWORDS = {Vergil ; Ausonius ; authorship verification ; Latin poetry ; cento ; computational poetics ; stylometry},
  PDF = {https://inria.hal.science/hal-05881529v1/file/CHR___Cento_Nuptialis.pdf},
  HAL_ID = {hal-05881529},
  HAL_VERSION = {v1},
}
```


## Setup: Latin scansion (rescan_joint)

`pycento/generate.py`'s `rescan_joint()` (used by `step-04`/`step-05` to
re-validate a merged/glued line's scansion) needs the
[`latin_scansion`](https://github.com/CUNY-CL/latin_scansion) FST engine with
a compiled grammar archive. `pip install latin-scansion` (already in
`requirements.txt`) only installs the Python library -- it does **not**
include a usable grammar. Two extra pieces are required:

1. **`pynini`** (the FST runtime `latin_scansion` is built on):

   ```bash
   env/bin/pip install pynini
   ```

   This has a `manylinux` wheel on PyPI, so plain `pip install` is enough --
   no conda needed.

2. **`thrax`** (the grammar *compiler*, `thraxcompiler` -- only needed to
   build the grammar once, not at runtime). There's no PyPI package for
   this; build it from source against Ubuntu's own OpenFst package:

   ```bash
   sudo apt install build-essential libfst-dev libfst-tools
   curl -LO https://www.opengrm.org/twiki/pub/GRM/ThraxDownload/thrax-1.3.10.tar.gz
   tar xzf thrax-1.3.10.tar.gz && cd thrax-1.3.10
   ./configure
   make -j
   sudo make install
   sudo ldconfig   # registers the newly-installed libthrax.so -- don't skip this
   ```

   Thrax 1.3.10 requires `openfst==1.8.4`, which matches Ubuntu 24.04/26.04's
   `libfst-dev` package version exactly, so no separate OpenFst build is
   needed. If you can't run `sudo ldconfig` (no root), work around it with
   `LD_LIBRARY_PATH=/usr/local/lib:/usr/local/lib/x86_64-linux-gnu` when
   invoking `make`/`thraxcompiler` below -- but running `ldconfig` properly
   is the real fix.

3. **Fetch the grammar source and compile it:**

   ```bash
   scripts/fetch_latin_scansion.sh          # clones CUNY-CL/latin_scansion into vendor/
   make -j -C vendor/latin_scansion/grammars
   ```

   This produces `vendor/latin_scansion/grammars/all.far`, the compiled
   grammar archive. `pycento/scansion.py` looks for it there by default;
   override the location with the `CENTO_SCANSION_FAR` environment variable
   if you put it somewhere else. `vendor/` is gitignored -- this is a local
   build artifact, not something to commit.

**Verify it worked:**

```bash
PYTHONPATH=. env/bin/python -c "
from pycento.scansion import is_valid_hexameter
print(is_valid_hexameter('arma virumque canō trojae quī prīmus ab ōris'))
"
```
Should print `True`. If it raises `pycento.scansion.ScansionUnavailable`, the
`all.far` isn't where it's expected -- re-check step 3. If it raises
`ModuleNotFoundError: No module named 'pynini'`, re-check step 1.

Without this set up, `step-04`/`step-05` still work, but require passing
`--allow-unchecked-merges` (merges of independently-chosen segments won't be
re-validated).

## Plan

Add more authors for the Benchmark, Statius, Silius A., Prudentius

- Benchmark POS/Lemma on one 1 book of the eclogues of each author
- Benchmark all the stylometry thingies on the eclogues of each author
- Benchmark all the stylometry thingies on Cento
- Simulate Centos and check if we can get away from the style of Virgile ?
	- Check Proba's Cento ?
