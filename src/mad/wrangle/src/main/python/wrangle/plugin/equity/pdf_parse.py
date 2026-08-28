import json
import sys

import pdftotext


def parse(pdf_path):
    with open(pdf_path, "rb") as pdf_file:
        return list(pdftotext.PDF(pdf_file, physical=True))


if __name__ == "__main__":
    json.dump(parse(sys.argv[1]), sys.stdout)
