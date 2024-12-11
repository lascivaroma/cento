import glob
import os
import bs4
import lxml.etree as et
import requests
import tqdm

pbar = tqdm.tqdm(total=len(glob.glob("*.html")))
for file in glob.glob("*.html"):
    pbar.set_description(f"File: {file}")
    req = requests.get(f"https://hypotactic.com/latin/{file}")
    html = bs4.BeautifulSoup(req.text)

    # Parse the HTML content
    soup = bs4.BeautifulSoup(req.text.encode('latin1').decode('utf-8'), 'html.parser')

    # Remove the head section
    if soup.head:
        soup.head.decompose()

    with open(file, "w") as f:
        f.write(str(soup))

    pbar.update(1)