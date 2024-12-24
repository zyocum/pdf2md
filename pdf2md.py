#!/usr/bin/env python3

"""Script for converting PDF to Markdown via OpenAI's `gpt-4o` model."""

import backoff
import base64
import os
import sys

from contextlib import closing
from getpass import getpass
from io import BytesIO
from openai import (
    OpenAI,
    RateLimitError
)
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
from tqdm import tqdm

# fallback to prompting user for OpenAI API key if not set in environment
api_key = os.environ.get('OPENAI_API_KEY') or getpass(prompt='OpenAI API key:')

openai = OpenAI(api_key=api_key)

@backoff.on_exception(backoff.expo, RateLimitError)
def completions_with_backoff(**kwargs):
    """OpenAI chat completions wrapper that will retry with a backoff strategy when encountering API rate limits"""
    return openai.chat.completions.create(**kwargs)

def page_image2md(page_image):
    """Prompt OpenAI `gpt-4o` model to generate Markdown text from given PIL.Image"""
    # encode image with base64 url encoding in order to pass it to the OpenAI API
    with BytesIO() as buffer:
        page_image.save(buffer, format=page_image.format)
        url_encoded_image = (
            f'data:image/{page_image.format.lower()};'
            f'base64,{base64.b64encode(buffer.getvalue()).decode("utf8")}'
        )
    # get completions from OpenAI API
    response = completions_with_backoff(
        model="gpt-4o",
        seed=0,
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": "You are a system that expertly extracts the contents of documents into textual representations as Markdown.",
                    },
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Convert the following image of a page from a PDF document to Markdown.  "
                            "Include all headings, paragraphs, lists, tables, etc.  "
                            "Ensure markup is included as necessary such as bold, italics, super- or sub-scripts, etc.  "
                            "Include additional notation as necessary such as mathematical notation in LaTeX math mode, code in pre-formatted blocks, etc.  "
                            "The output should be Markdown itself (don't preformat the output in a markdown block), and exclude local or hyperlinked images.  "
                            "I.e., don't include a block like ```markdown ...``` wrapping the entire page (unless the entire page's content is actually Markdown source).  "
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": url_encoded_image,
                        },
                    },
                ],
            }
        ],
        max_tokens=16384, # current maximum token limit
    )
    return response

def get_page_images(
    pdf_path,
    cache_pages=False,
    first_page=None,
    last_page=None,
    page_dpi=200,
    page_image_format='PNG',
):
    """Generate PIL.Images for each page of the given PDF file.

    PDF page images can be cached to avoid regenerating them for every run.
    A range of pages can also be specified via the {first,last}_page keyword paramaters.
    The resolution of the images can be specified in dots-per-inch (DPI) via the page_dpi.
    """
    pdf_pages_cache_directory = pdf_path.with_suffix('')
    if cache_pages and pdf_pages_cache_directory.is_dir():
        for path in sorted(pdf_pages_cache_directory.glob(f'*.{page_image_format.lower()}')):
            path = Path(path)
            if path.is_file():
                with Image.open(path) as image:
                    yield image
    else:
        if cache_pages:
            pdf_pages_cache_directory.mkdir(parents=True, exist_ok=True)
        yield from convert_from_path(
            pdf_path,
            first_page=first_page,
            last_page=last_page,
            output_folder=(pdf_pages_cache_directory if cache_pages else None),
            output_file=pdf_path,
            dpi=page_dpi,
            fmt=page_image_format,
            thread_count=8,
        )

def main(
    pdf_path,
    cache_pages=False,
    first_page=None,
    last_page=None,
    page_dpi=200,
    page_image_format='PNG',
    output_file=sys.stdout,
    page_sep=('\n' * 3) + ('-' * 10) + ('\n' * 3),
):
    with closing(output_file) as md_file:
        with tqdm(
            get_page_images(
                pdf_path,
                cache_pages=cache_pages,
                first_page=first_page,
                last_page=last_page,
                page_dpi=page_dpi,
                page_image_format=page_image_format,
            ),
            unit='page',
        ) as images:
            for image in images:
                completions = page_image2md(image)
                markdown = completions.choices[0].message.content
                print(markdown, file=md_file, flush=True, end=page_sep)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description=__doc__
    )
    parser.add_argument(
        'pdf',
        type=Path,
        help='path to input PDF file to convert to Markdown'
    )
    parser.add_argument(
        'output',
        nargs='?',
        type=argparse.FileType('w'),
        default=sys.stdout,
        help='output file where Markdown conversion will be written (or stdout)',
    )
    parser.add_argument(
        '-c', '--cache-pages',
        default=False,
        action='store_true',
        help='cache and reuse intermediate PDF page images',
    )
    parser.add_argument(
        '--first-page',
        type=int,
        default=None,
        help='the first page to convert',
    )
    parser.add_argument(
        '--last-page',
        type=int,
        default=None,
        help='the last page to convert',
    )
    parser.add_argument(
        '--dpi',
        type=int,
        default=200,
        help='intermediate image resolution in dots-per-inch (DPI) (higher DPI is higher quality, but takes more memory/disk space)',
    )
    args = parser.parse_args()
    main(
        args.pdf,
        cache_pages=args.cache_pages,
        first_page=args.first_page,
        last_page=args.last_page,
        page_dpi=args.dpi,
        output_file=args.output,
    )
