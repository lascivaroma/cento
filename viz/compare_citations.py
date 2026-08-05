import os
import glob

import lxml.etree as et
from dataclasses import dataclass
from collections import Counter
from typing import List
from functools import lru_cache
import numpy as np
import pandas as pd
import statsmodels.api as sm
import matplotlib.pyplot as plt

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

@dataclass
class Segment:
    scan: str = ""
    start_a_line: bool = False # Whether the segment starts a line
    more_than_a_line: bool = False
    urn: str = ""


def path(string: str) -> str:
    return os.path.join(os.path.dirname(__file__), string)

cento = et.parse(path("../data/generated-compact/cento-compact.xml"))
urns = Counter([str(value) for value in cento.xpath("//@source")])

def get_template(cento):
    template: List[Segment] = []

    for row in cento.xpath("//line"):
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
                    segment.urn += ";"+elem.attrib["source"]
                else:
                    segment = Segment(start_a_line=first_segment, scan="/" if first_segment else "", urn=elem.attrib["source"])
                    template.append(segment)
                if first_segment:
                    first_segment = False
            elif elem.tag == "word":
                segment.scan += elem.attrib["sy"]
    return template

def get_uniques(template):
    uniques = {element.scan: [] for element in template}
    xml_virgil = et.parse(path("../data/generated-compact/virgil-compact.xml"))
    for scan in uniques:
        for poem in xml_virgil.xpath("./div/div"):
            # For full line, it's simple, we get the line scan and check a match with our current one
            if scan[0] == "/" and scan.count("/") == 1 and "1" in scan and "6" in scan:
                for line in poem.xpath("./line"):
                    line_scan = _line_scan(line)
                    if line_scan == scan:
                        uniques[scan].append(1)
            # For double line, still simple: we first check if a line match the first of our line (.startswith)
            #   and then we check the second one
            elif scan[0] == "/" and scan.count("/") == 2 and scan.count("1A") == 2 and scan.count("6A") == 2:
                lines = poem.xpath("./line")
                lid = 0
                while lid < len(lines):
                    line = lines[lid]
                    line_scan = _line_scan(line)
                    if scan.startswith(line_scan) and lid < len(lines) - 1:
                        next_line_scan = _line_scan(lines[lid + 1])
                        if line_scan + next_line_scan == scan:
                            uniques[scan].append(1)
                    lid += 1
            # We single out the case of line starts: we get the full line scan to filter them out based on a startwith
            #   Then we progressively scan until it starts with the right start
            #   And just in case, we match completely the same scan (because a word can go hover a D/S split).
            elif scan.startswith("/") and scan.count("/") == 1:  # Single line start
                for line in poem.xpath("./line"):
                    line_scan = _line_scan(line)
                    if line_scan.startswith(scan):
                        temp_scan = "/"
                        words = []
                        line_words = line.xpath("./word")
                        wid = 0
                        while wid < len(line_words):
                            elem = line_words[wid]
                            temp_scan += elem.attrib["sy"]
                            words.append(elem)
                            if temp_scan.startswith(scan):  # We stop when one contains the other
                                break
                            wid += 1
                        if temp_scan == scan:  # We check that it's a strict equality
                            uniques[scan].append(1)
            # Reverse of the first one
            elif not scan.startswith("/") and scan.count("/") == 0:  # Single line end
                for line in poem.xpath("./line"):
                    if words := _tail_scan_matching(line, scan):
                        uniques[scan].append(1)
            # We got the full line followed by a bit
            elif scan.startswith("/") and scan.count("/") == 2:  # Single line start
                lines = poem.xpath("./line")
                lid = 0
                while lid < len(lines) - 1:
                    line = lines[lid]
                    line_scan = _line_scan(line)
                    # If our first line matches, we go into the second line
                    if scan.startswith(line_scan):
                        next_line_scan = _line_scan(lines[lid + 1])
                        # Now we match if the two lines starts with the pattern with search
                        if (line_scan + next_line_scan).startswith(scan):
                            temp_scan = line_scan + "/"  # We start with the second one already
                            words = []
                            wid = 0
                            line_words = lines[lid + 1].xpath("./word")
                            while wid < len(line_words):
                                elem = line_words[wid]
                                temp_scan += elem.attrib["sy"]
                                words.append(elem)
                                if temp_scan.startswith(scan):  # We stop when one contains the other
                                    break
                                wid += 1
                            if temp_scan == scan:  # We check that it's a strict equality
                                uniques[scan].append(1)
                    lid += 1
            elif not scan.startswith("/") and scan.count("/") == 1:
                lines = poem.xpath("./line")
                lid = 0
                while lid < len(lines) - 1:  # We stop earlier because we need two consecutive lines
                    line = lines[lid]
                    first_segment, second_segment = scan.split("/")
                    second_segment = "/" + second_segment
                    if words := _tail_scan_matching(line, first_segment):  # We match the first element
                        next_line_scan = _line_scan(lines[lid + 1])
                        if "6" in second_segment:  # We got a full line for the second part
                            if next_line_scan == second_segment:  # We got a full line as second segment, let's go
                                uniques[scan].append(1)
                        elif next_line_scan.startswith(second_segment):
                            temp_scan = "/"
                            words_seg_2 = []
                            second_line_words = lines[lid + 1].xpath("./word")
                            wid = 0
                            while wid < len(second_line_words):
                                elem = second_line_words[wid]
                                temp_scan += elem.attrib["sy"]
                                words_seg_2.append(elem)
                                if temp_scan.startswith(second_segment):  # We stop when one contains the other
                                    break
                                wid += 1
                            if temp_scan == second_segment:  # We check that it's a strict equality
                                uniques[scan].append(1)

                    lid += 1
            else:
                print(f"Missing for {scan}")
    uniques = {scan: sum(values) for scan, values in uniques.items()}
    return uniques

template = get_template(cento)
uniques = get_uniques(template)
urn_to_scan = {
    urn: segment.scan
    for segment in template
    for urn_idx, urn in enumerate(segment.urn.split(";"))
}


def get_a_distrib(form)->dict:
    data = {urn: [] for urn in urns}

    for poem in glob.glob(path(f"../data/generated-compact/{form}/*.xml")):
        local_urns = Counter(map(str, et.parse(poem).xpath("//@source")))
        for urn in urns:
            data[urn].append(local_urns[urn])

    data = {
        key: sum(value)
        for key, value in sorted(list(data.items()), key=lambda x: sum(x[1]))
    }
    return data

EXACT = get_a_distrib("exact")
LOOSE = get_a_distrib("loose")

from scipy import stats
# for element in EXACT:
#     print(element, EXACT[element], len(uniques[urn_to_scan[element]]))

for element in LOOSE:
    print(element, LOOSE[element], uniques[urn_to_scan[element]])

def get_pearson_spearman(key, form)->dict:
    pool_sizes = []
    rates = []

    for element in form:
        pool = uniques[urn_to_scan[element]]
        rate = form[element]
        pool_sizes.append(pool)
        rates.append(rate)

    pearson_r, pearson_p = stats.pearsonr(pool_sizes, rates)
    spearman_r, spearman_p = stats.spearmanr(pool_sizes, rates)
    print(f"=> {key}")
    print(f"Pearson:  r={pearson_r:.3f}, p={pearson_p:.4f}")
    print(f"Spearman: r={spearman_r:.3f}, p={spearman_p:.4f}")

get_pearson_spearman("RQ2", EXACT)
get_pearson_spearman("RQ3", LOOSE)


def diagnose_rarity_correlation(
    obs,
    uniques,
    urn_to_scan,
    label="RQ2",
    save_path=None,
):
    """
    Build pool_size / rate pairs from `obs` and run log-linear regression
    diagnostics: fitted-line scatter, residuals vs fitted, residuals vs
    log(pool_size), Q-Q plot, and a quadratic-term significance check.

    Parameters
    ----------
    obs : dict
        Element -> apparition rate (e.g. EXACT for RQ2 or RQ3).
    uniques : dict
        Urn -> collection of unique known phenomena (pool).
    urn_to_scan : dict
        Element -> urn key, used to look up uniques[urn_to_scan[element]].
    label : str
        Used in plot titles and printed output (e.g. "RQ2", "RQ3").
    save_path : str or None
        If given, path to save the figure (e.g. "/home/claude/rq2_diag.png").
        If None, the figure is not saved, only shown.

    Returns
    -------
    df : pandas.DataFrame
        Columns: element, pool_size, rate, log_pool_size, predicted, residual.
    model : statsmodels.regression.linear_model.RegressionResultsWrapper
        The fitted quadratic OLS model (const, log_pool, log_pool_sq).
    """
    # --- 0. Build the dataframe ---
    rows = []
    for element in obs:
        pool = uniques[urn_to_scan[element]]
        rate = obs[element]
        rows.append({"element": element, "pool_size": pool, "rate": rate})

    df = pd.DataFrame(rows)
    df["log_pool_size"] = np.log1p(df["pool_size"])

    # --- 1. Fit the log-linear regression ---
    slope, intercept, r_value, p_value, std_err = stats.linregress(
        df["log_pool_size"], df["rate"]
    )
    df["predicted"] = slope * df["log_pool_size"] + intercept
    df["residual"] = df["rate"] - df["predicted"]

    print(f"[{label}] Fit: rate = {slope:.4f} * log(pool_size+1) + {intercept:.4f}")
    print(f"[{label}] r={r_value:.3f}, p={p_value:.4g}, std_err={std_err:.4f}")

    # --- 2. Plot: fit + residuals + residuals vs x + QQ ---
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # (a) Scatter with fitted line
    x_line = np.linspace(df["log_pool_size"].min(), df["log_pool_size"].max(), 100)
    y_line = slope * x_line + intercept
    axes[0, 0].scatter(df["log_pool_size"], df["rate"], alpha=0.6, edgecolor="k", linewidth=0.3)
    axes[0, 0].plot(x_line, y_line, color="red", linewidth=2, label=f"fit (r={r_value:.2f})")
    axes[0, 0].set_xlabel("log(pool_size + 1)")
    axes[0, 0].set_ylabel("apparition rate")
    axes[0, 0].set_title(f"{label}: rate vs log(pool_size) with fit")
    axes[0, 0].legend()

    # (b) Residuals vs fitted — look for a curved band (leftover nonlinearity)
    # or a funnel shape (heteroscedasticity)
    axes[0, 1].scatter(df["predicted"], df["residual"], alpha=0.6, edgecolor="k", linewidth=0.3)
    axes[0, 1].axhline(0, color="red", linestyle="--")
    axes[0, 1].set_xlabel("predicted rate")
    axes[0, 1].set_ylabel("residual")
    axes[0, 1].set_title("Residuals vs fitted\n(look for curvature or funnel shape)")

    # (c) Residuals vs log(pool_size) directly — best view for threshold effects
    # at small pool sizes specifically
    axes[1, 0].scatter(df["log_pool_size"], df["residual"], alpha=0.6, edgecolor="k", linewidth=0.3)
    axes[1, 0].axhline(0, color="red", linestyle="--")
    axes[1, 0].set_xlabel("log(pool_size + 1)")
    axes[1, 0].set_ylabel("residual")
    axes[1, 0].set_title("Residuals vs log(pool_size)\n(look for a bend at small pools)")

    # (d) QQ plot — checks if residuals are roughly normal
    # (matters if you plan to trust the p-value / CI from the linear fit)
    stats.probplot(df["residual"], dist="norm", plot=axes[1, 1])
    axes[1, 1].set_title("Q-Q plot of residuals")

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
    plt.show()

    # --- 3. Quantitative curvature check: add a squared term ---
    # If log(pool_size)^2 adds real explanatory power, the log-linear fit
    # alone is missing curvature.
    X = pd.DataFrame({
        "log_pool": df["log_pool_size"],
        "log_pool_sq": df["log_pool_size"] ** 2,
    })
    X = sm.add_constant(X)
    model = sm.OLS(df["rate"], X).fit()

    print(f"\n--- [{label}] Quadratic term check ---")
    print(model.summary())
    print(
        f"\n[{label}] If 'log_pool_sq' is significant (p<0.05), there's "
        "meaningful curvature the simple log-linear fit is missing."
    )

    return df, model

diagnose_rarity_correlation(EXACT, uniques, urn_to_scan, label="RQ2", save_path=path("rq2_scatter.png"))
diagnose_rarity_correlation(LOOSE, uniques, urn_to_scan, label="RQ3", save_path=path("rq3_scatter.png"))

