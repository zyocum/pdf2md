#!/usr/bin/env python3

"""Script for converting PDF to Markdown via OpenAI's `gpt-4o` model."""

import asyncio
import base64
import os
import sys
from contextlib import closing
from getpass import getpass
from io import BytesIO
from itertools import islice
from pathlib import Path
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    TextIO,
    Tuple,
)

import backoff
import openai
from openai.types.chat.chat_completion import ChatCompletion
from pdf2image import convert_from_path
from PIL import Image
from tqdm import tqdm

@backoff.on_exception(backoff.expo, openai.RateLimitError)
async def completions_with_backoff(
    client: openai.AsyncOpenAI,
    **kwargs: Dict[str, Dict[str, Any]]
) -> ChatCompletion:
    """OpenAI chat completions wrapper that will retry with a backoff strategy when encountering API rate limits"""
    return await client.chat.completions.create(**kwargs)

async def page_image2md(
    page_image: Image.Image,
    client: openai.AsyncOpenAI
) -> ChatCompletion:
    """Prompt OpenAI `gpt-4o` model to generate Markdown text from given PIL.Image"""
    # encode image with base64 url encoding in order to pass it to the OpenAI API
    with BytesIO() as buffer:
        page_image.load()
        format = page_image.format or 'PNG'
        page_image.save(buffer, format=format)
        url_encoded_image = (
            f'data:image/{format.lower()};'
            f'base64,{base64.b64encode(buffer.getvalue()).decode("utf8")}'
        )
    # get completions from OpenAI API
    response = await completions_with_backoff(
        client,
        model='gpt-4.1',
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
    pdf_path: Path,
    cache_pages: bool = False,
    first_page: int = None,
    last_page: int = None,
    page_dpi: int = 200,
    page_image_format: str = 'PNG',
    thread_count: int = 8,
) -> Generator[Image.Image]:
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
                    image.load()
                    yield image
    else:
        if cache_pages:
            pdf_pages_cache_directory.mkdir(parents=True, exist_ok=True)
        for image in convert_from_path(
            pdf_path,
            first_page=first_page,
            last_page=last_page,
            output_folder=(pdf_pages_cache_directory if cache_pages else None),
            output_file=pdf_path,
            dpi=page_dpi,
            fmt=page_image_format,
            thread_count=thread_count,
        ):
            image.load()
            yield image

def batches(
    iterable: Iterable[Any],
    n: int
) -> Iterable[Tuple[Any]]:
    """Lazily yield tuples of size n from iterable.
    
    The last iterable may be smaller than n.
    """
    iterable = iter(iterable)
    while True:
        batch = tuple(islice(iterable, 0, n))
        if batch:
            yield batch
        else:
            break

async def main(
    pdf_path: Path,
    cache_pages: bool = False,
    first_page: int = None,
    last_page: int = None,
    page_dpi: int = 200,
    page_image_format: str = 'PNG',
    concurrency: int = 8,
    output_file: TextIO = sys.stdout,
    page_sep: str = ('\n' * 3) + ('-' * 10) + ('\n' * 3),
):
    # instantiate OpenAI client
    api_key = os.environ.get('OPENAI_API_KEY') or getpass(prompt='OpenAI API key:')
    client = openai.AsyncOpenAI(api_key=api_key)

    pages = get_page_images(
        pdf_path,
        cache_pages=cache_pages,
        first_page=first_page,
        last_page=last_page,
        page_dpi=page_dpi,
        page_image_format=page_image_format,
        thread_count=concurrency,
    )
    with closing(output_file) as md_file:
        with tqdm(unit='page') as progress:
            for batch in batches(pages, concurrency):
                tasks = [page_image2md(img, client) for img in batch]
                responses = await asyncio.gather(*tasks)
                for response in responses:
                    markdown = response.choices[0].message.content
                    print(markdown, file=md_file, flush=True, end=page_sep)
                    progress.update(1)

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
    parser.add_argument(
        '-n', '--concurrency',
        type=int,
        default=8,
        help='number of pages to process in parallel',
    )
    args = parser.parse_args()
    # run the async pipeline
    asyncio.run(
        main(
            args.pdf,
            cache_pages=args.cache_pages,
            first_page=args.first_page,
            last_page=args.last_page,
            page_dpi=args.dpi,
            concurrency=args.concurrency,
            output_file=args.output,
        )
    )
