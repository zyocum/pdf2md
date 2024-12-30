# `pdf2md.py`

Convert PDF to Markdown via OpenAI's multi-modal text/vision model.

## Setup

### OpenAI API Access

Acquire an OpenAI API key from [here](https://platform.openai.com/signup).

Add your Open API key to your environment (if it's not defined already):

```zsh
$ export OPENAI_API_KEY="sk-..." # your key will look like "sk-..."
```

### Azure OpenAI API Access

Acquire an Azure OpenAI API key and endpoint from the Azure portal.

Add your Azure OpenAI API key and endpoint to your environment (if they are not defined already):

```zsh
$ export AZURE_OPENAI_API_KEY="your-azure-api-key"
$ export AZURE_OPENAI_ENDPOINT="your-azure-endpoint"
```

### `poppler`

Install [`poppler`](https://poppler.freedesktop.org) for your system (for handling PDF to image conversion).

E.g., on macOS via the [Homebrew](https://brew.sh) package manager:

```zsh
$ brew install poppler
...
```

On Ubuntu/Debian systems:

```zsh
$ sudo apt-get install poppler-utils
...
```

For other Linux distributions, use their respective package managers:
- Fedora/RHEL: `sudo dnf install poppler-utils`
- Arch Linux: `sudo pacman -S poppler`

### Python Dependencies

Then create a virtual environment and install the Python dependencies:

```zsh
$ python -m venv pdf2md
$ source pdf2md/bin/activate
(pdf2md) $ pip install -U pip
...
(pdf2md) $ pip install -r requirements.txt
...
```

## Usage
```zsh
(pdf2md) $ ./pdf2md.py --help
usage: pdf2md.py [-h] [-c] [--first-page FIRST_PAGE] [--last-page LAST_PAGE] [--dpi DPI] pdf [output]

Script for converting PDF to Markdown via OpenAI's `gpt-4o` model.

positional arguments:
  pdf                   path to input PDF file to convert to Markdown
  output                output file where Markdown conversion will be written (or stdout) (default:
                        <_io.TextIOWrapper name='<stdout>' mode='w' encoding='utf-8'>)

options:
  -h, --help            show this help message and exit
  -c, --cache-pages     cache and reuse intermediate PDF page images (default: False)
  --first-page FIRST_PAGE
                        the first page to convert (default: None)
  --last-page LAST_PAGE
                        the last page to convert (default: None)
  --dpi DPI             intermediate image resolution in dots-per-inch (DPI) (higher DPI is higher quality, but
                        takes more memory/disk space) (default: 200)
```

## Example

You can download an example PDF to convert from [here](https://api.slingacademy.com/v1/sample-data/files/text-and-table.pdf):

```zsh
(pdf2md) $ curl -so text-and-table.pdf 'https://api.slingacademy.com/v1/sample-data/files/text-and-table.pdf'
(pdf2md) $ ./pdf2md.py text-and-table.pdf > text-and-table.pdf.md
2page [00:03, 1.52s/page]
(pdf2md) $ cat text-and-table.pdf.md
# Sample PDF File for Practice

## Page 1: Table Data

The table below displays information about some fictional people:

| First Name | Last Name | Age |
|------------|-----------|-----|
| John       | Doe       | 99  |
| Jane       | Doo       | 29  |
| Black      | Smith     | 49  |
| Lone       | Wolf      | 35  |
| Foo        | Bar       | 5   |
| Sekiro     | Honda     | 45  |
| Elon       | Musk      | 54  |
| Catherine  | Roth      | 55  |
| Julio      | Caesar    | 58  |
| Candy      | Sweet     | 6   |
| Bo         | Kim       | 32  |
| Sling      | Academy   | 44  |
| Rantaro    | Shinsuke  | 9   |
| Cold       | Water     | 15  |
| Fried      | Chicken   | 3   |
| Blonde     | Pink      | 23  |

This PDF file has one more page. Don’t miss it.


----------


# Page 2

Welcome to [www.slingacademy.com](https://www.slingacademy.com). You can find more sample data at [https://www.slingacademy.com/cat/sample-data/](https://www.slingacademy.com/cat/sample-data/)

Happy coding & have a nice day!


----------
```

Output Markdown file: [text-and-table.pdf.md](text-and-table.pdf.md)

If you want to save intermediate PNG images of the PDF pages, use the `-c/--cache-pages` options (this can speed things up a little bit if you want to rerun a conversion of a large PDF, though OpenAI API rate limits may still be the rate-limiting factor).

```zsh
(pdf2md) $ ./pdf2md.py text-and-table.pdf --cache-pages > text-and-table.pdf.md
2page [00:03, 1.52s/page]
(pdf2md) $ ls text-and-table
text-and-table.pdf0001-1.png text-and-table.pdf0002-2.png
```

## Known Issues

1. PDFs that contain images cannot be faithfully fully converted since images are not extracted.  Headings, lists, paragraphs, code-blocks and other basic markup that is compatible with Markdown should work, though.

2. Each page of the input PDF is processed independently of the others, so it's possible that some context is lost from page to page (e.g., header levels) in multi-page PDFs.  As such, adjacent pages may be slightly incoherent in their markup compared to the original document.

3. OpenAI may enforce rate limits on your account both for requests per unit time and completion tokens generated per unit time, so if you try to process large PDFs with many pages, or even many short PDFs, the script will wait and retry for you, but it may be slow to wait for your rate limits to expire.
