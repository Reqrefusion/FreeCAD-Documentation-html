# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileNotice: Part of the Offline Wiki addon.

import os
import re
import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
import random

# API URL
wiki_url = "https://wiki.freecad.org/api.php"
css_modules_urls = [
    "https://wiki.freecad.org/load.php?lang=tr&modules=site.styles|ext.pygments%2Ctranslate|ext.translate.edit.documentation.styles|ext.translate.tag.languages|ext.uls.pt|jquery.makeCollapsible.styles|mediawiki.ui.button%2Cicon|skins.vector.icons%2Cstyles&only=styles&skin=vector-2022",
]
js_modules_urls = [
    "https://wiki.freecad.org/load.php?lang=tr&modules=startup&only=scripts&raw=1&skin=vector-2022",
    "https://wiki.freecad.org/load.php?lang=tr&modules=ext.uls.common%2Ccompactlinks%2Cinterface%2Cpreferences%2Cwebfonts%7Cjquery%2Coojs%2Csite%7Cjquery.client%2Ccookie%2CmakeCollapsible%7Cjquery.uls.data%7Cmediawiki.String%2CTitle%2Capi%2Cbase%2Ccldr%2Ccookie%2Cexperiments%2CjqueryMsg%2Clanguage%2Cstorage%2Ctoc%2Cuser%2Cutil%7Cmediawiki.libs.pluralruleparser%7Cmediawiki.page.ready%7Cmediawiki.page.watch.ajax%7Cskins.vector.es6%2Cjs%7Cskins.vector.icons.js&skin=vector-2022&version=1xtov",
    "https://wiki.freecad.org/load.php?lang=tr&modules=ext.uls.webfonts.repository&skin=vector-2022&version=inkny",
]

output_dir = "wiki"

# Supported language codes
language_codes = [
    'bg', 'cs', 'de', 'en', 'es', 'fi', 'fr', 'hr', 'hu', 'id', 'it', 'ja',
    'ko', 'pl', 'pt', 'pt-br', 'ro', 'ru', 'sk', 'sv', 'tr', 'uk', 'vi', 'zh', 'zh-cn', 'zh-tw'
]


# Functions

def sanitize_name(name):
    """Cleans file names."""
    return name.replace(' ', '_').replace(':', ';').strip()

def remove_first_segment(text, delimiter):
    parts = text.split(delimiter)
    return delimiter.join(parts[1:])

def create_file_path(title):
    """Creates the correct file path based on the page title and language."""
    parts = [part for part in title.split('/') if part]

    # If the title has multiple parts and the last part is in language codes, check the language code
    if len(parts) > 1 and parts[-1] in language_codes:
        language_code = parts[-1]  # Last part is the language code
        content_parts = parts[:-1]  # Remaining parts are content
    else:
        language_code = None  # No language code
        content_parts = parts  # All title parts form the content

    # Create the file name
    sanitized_content = [sanitize_name(part) for part in content_parts]

    if language_code:
        # If a different language code exists, save to the respective language folder
        file_name = '_'.join(sanitized_content) + ".html"
        return os.path.join(output_dir, language_code, file_name)
    else:
        # If there is no language code, save to the default folder
        file_name = '_'.join(sanitized_content) + ".html"
        return os.path.join(output_dir, file_name)

def download_css_js():
    """Downloads and saves all CSS and JS files."""
    os.makedirs(output_dir, exist_ok=True)

    # Download the CSS file
    css_file = os.path.join(output_dir, "site.css")
    if not os.path.exists(css_file):
        print("Downloading and merging CSS files...")
        css_content = ""
        for url in css_modules_urls:
            css_content += requests.get(url).text + "\n"
        with open(css_file, 'w', encoding='utf-8') as f:
            f.write(css_content)

    # Download the JS file
    js_file = os.path.join(output_dir, "site.js")
    if not os.path.exists(js_file):
        print("Downloading and merging JS files...")
        js_content = ""
        for url in js_modules_urls:
            js_content += requests.get(url).text + "\n"
        with open(js_file, 'w', encoding='utf-8') as f:
            f.write(js_content)

def adjust_links(html_content, page_title):
    """Updates the links in the HTML content according to the local file structure."""
    soup = BeautifulSoup(html_content, 'html.parser')
    num_slashes = page_title.count('/')
    if num_slashes < 0:
        num_slashes = 0

    # Adjust all <a> tags' href attributes
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if href.startswith('/File:'):
            file_name = href.split('/File:')[-1]
            a_tag['href'] = f"{'../' * num_slashes}File/{file_name}"
        elif href.startswith('/wiki/'):
            relative_link = href.split('/wiki/')[-1]
            file_path = create_file_path(relative_link)  # Use create_file_path function to create the file path
            a_tag['href'] = file_path
        elif href.startswith('/'):
            parts = href.split('#')

            a_tag['href'] = a_tag['href'] = ('../' * num_slashes) + remove_first_segment(create_file_path(parts[0]), '\\')  # Correct links starting from the root
            if len(parts) > 1:
                a_tag['href'] += '#' + parts[-1]

    # Adjust all <img> tags' src attributes
    for img_tag in soup.find_all('img', src=True):
        src = img_tag['src']
        if src.startswith('/'):
            file_name = src.split('/')[-1]
            file_name = re.sub(r'^\d+px-', '', file_name)  # Remove prefix like '123px-' if present
            img_tag['src'] = f"{'../' * num_slashes}File/{file_name}"
        else:
            print(f"Warning: Unexpected image src format: {src}")
            continue  # Skip unexpected src formats

        # Remove srcset attribute if present
        if 'srcset' in img_tag.attrs:
            del img_tag['srcset']

    return str(soup)


def process_page(page):
    """Processes and saves the content of a page."""
    page_title = page['title']
    if page_title.endswith("/en"):
        page_title = page_title[:-3]

    # Create the file path
    file_path = create_file_path(page_title)

    # Skip if the file already exists
    if os.path.exists(file_path):
        print(f"'{file_path}' already exists, skipping.")
        return

    # Fetch the page content as HTML
    print(f"Fetching content: {page_title}")
    content_params = {
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "disableeditsection": "true",
        "format": "json"
    }
    response = requests.get(wiki_url, params=content_params)

    if response.status_code != 200:
        print(f"Error: Could not download {page_title}. HTTP Code: {response.status_code}")
        return

    data = response.json()
    html_content = data.get('parse', {}).get('text', {}).get('*', '')

    if not html_content:
        print(f"Content for '{page_title}' is empty, skipping.")
        return

    num_slashes = page_title.count('/')
    if num_slashes < 0:
        num_slashes = 0

    # Add CSS and JS files to the HTML
    css_link = f'<link rel="stylesheet" type="text/css" href="{("../" * num_slashes)}site.css">\n'
    js_script = f'<script src="{("../" * num_slashes)}site.js"></script>\n'
    beforehtml_content = '<div class="mw-page-container">'
    afterhtml_content = '</div>'
    body_header = f'<h1 id="firstHeading" class="firstHeading mw-first-heading"><span class="mw-page-title-main">{page_title}</span></h1>'

    full_html = f"{css_link}{beforehtml_content}{body_header}{html_content}{afterhtml_content}{js_script}"

    # Correct links
    full_html = adjust_links(full_html, page_title)

    # Save the HTML file
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(full_html)

    print(f"Successfully saved '{page_title}': {file_path}")


# Main execution
download_css_js()

# Load pages from all_pages.json
if not os.path.exists("all_pages.json"):
    print("all_pages.json file not found!")
    exit()

with open("all_pages.json", 'r', encoding='utf-8') as f:
    all_pages = json.load(f)

# Shuffle the pages randomly to process in random order
random.shuffle(all_pages)

# Process each page
for page in all_pages:
    process_page(page)