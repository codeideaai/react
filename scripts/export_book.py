#!/usr/bin/env python3
"""Export the existing Quarto sources to a single PDF and/or EPUB."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parent.parent
READER = "markdown+fenced_divs+native_divs+native_spans"


def command(*argv, stdin=None, cwd=ROOT):
    return subprocess.run(argv, cwd=cwd, input=stdin, text=True, encoding="utf-8",
                          stdout=subprocess.PIPE, check=True).stdout


def entries(nodes):
    for node in nodes:
        if isinstance(node, str):
            yield node
        elif "href" in node:
            yield node["href"]
        elif "contents" in node:
            yield from entries(node["contents"])


def inline(text):
    return [{"t": "Str", "c": text}]


def walk(obj):
    if isinstance(obj, dict):
        if "t" in obj:
            yield obj
        for val in obj.values():
            yield from walk(val)
    elif isinstance(obj, list):
        for val in obj:
            yield from walk(val)


def source_selection(spec):
    website = yaml.safe_load((ROOT / "_quarto.yml").read_text(encoding="utf-8"))["website"]
    mode = spec["navigation"]
    if mode == "navbar":
        return list(entries(website["navbar"]["left"]))
    paths = list(entries(website["sidebar"]["contents"]))
    if "module_numbers" in spec:
        wanted = set(spec["module_numbers"])
        matches = [(int(m.group(1)), name) for name in paths
                   if (m := re.fullmatch(r"Module_(\d+)_.*\.md", name))]
        if not wanted <= {index for index, _ in matches}:
            raise ValueError("A book module is missing from the website sidebar")
        return [name for index, name in matches if index in wanted]
    return paths


def portable_links(blocks, source, chapter_ids):
    for node in walk(blocks):
        if node["t"] == "Link":
            target = node["c"][2][0]
            parts = urlsplit(target)
            if parts.scheme or parts.netloc or not target:
                continue
            source_path = unquote(parts.path)
            resolved = ((source.parent / source_path).resolve() if source_path else source)
            if resolved in chapter_ids:
                chapter_id = chapter_ids[resolved]
                fragment = unquote(parts.fragment)
                node["c"][2][0] = "#" + chapter_id + ("-" + fragment if fragment else "")
            elif resolved.suffix in (".qmd", ".md"):
                # A link to a page not in this edition remains legible, not a broken offline link.
                node.update(t="Span", c=[["", [], []], node["c"][1]])
        if node["t"] == "Image":
            target = node["c"][2][0]
            parts = urlsplit(target)
            if not parts.scheme and not parts.netloc and parts.path:
                node["c"][2][0] = str((source.parent / unquote(parts.path)).resolve())


def assemble(paths, spec):
    chapter_ids = {path: f"chapter-{i:02}" for i, path in enumerate(paths, 1)}
    result = None
    for source in paths:
        document = json.loads(command("pandoc", "-f", READER, "-t", "json", str(source)))
        if result is None:
            result = {"pandoc-api-version": document["pandoc-api-version"],
                      "meta": {"title": {"t": "MetaInlines", "c": inline(spec["title"])},
                               "lang": {"t": "MetaString", "c": "zh-CN"}}, "blocks": []}
        chapter_id = chapter_ids[source]
        blocks = document["blocks"]
        title = document["meta"].get("title", {})
        if title.get("t") == "MetaInlines":
            title = title["c"]
        else:
            raise ValueError(f"Missing chapter title in {source.relative_to(ROOT)}")
        if blocks and blocks[0]["t"] == "HorizontalRule":
            blocks = blocks[1:]
        portable_links(blocks, source, chapter_ids)
        for node in walk(blocks):
            if node["t"] == "Header":
                contents = node["c"]
                contents[0] = min(6, max(2, contents[0]))
                contents[1][0] = f"{chapter_id}-{contents[1][0]}"
            if node["t"] == "Div":
                attr, contents = node["c"]
                if any(c.startswith("callout-") for c in attr[1]):
                    label = dict(attr[2]).get("title")
                    if label:
                        contents.insert(0, {"t": "Para", "c": [{"t": "Strong", "c": inline(label)}]})

        result["blocks"].append({"t": "Header", "c": [1, [chapter_id, [], []], title]})
        result["blocks"].extend(blocks)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("pdf", "epub", "all"), default="all")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "_exports")
    args = parser.parse_args()
    spec = json.loads((ROOT / "scripts" / "book.json").read_text(encoding="utf-8"))
    formats = ("pdf", "epub") if args.format == "all" else (args.format,)
    for name in ("pandoc", "typst") if "pdf" in formats else ("pandoc",):
        if not shutil.which(name):
            parser.error(f"{name} is required but is not on PATH")
    paths = [(ROOT / p).resolve() for p in source_selection(spec)]
    if not paths or len(set(paths)) != len(paths):
        parser.error("no chapters or duplicate chapters in the selected website navigation")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".book-", dir=output) as directory:
        temp = Path(directory)
        document = assemble(paths, spec)
        data = json.dumps(document, ensure_ascii=False)
        common = ("pandoc", "-f", "json", "--standalone", "--toc", "--toc-depth=2")
        files = []
        if "epub" in formats:
            epub = temp / (spec["name"] + ".epub")
            command(*common, "--to=epub3", "--split-level=1", "-o", str(epub), stdin=data)
            files.append(epub)
        if "pdf" in formats:
            src = temp / "book.typ"
            pdf = temp / (spec["name"] + ".pdf")
            # Typst resolves embedded image paths inside the compilation root.
            for node in walk(document["blocks"]):
                if node["t"] == "Image":
                    target = Path(node["c"][2][0])
                    if target.is_absolute() and target.is_file():
                        if target.parent != temp:
                            assets = temp / "assets"
                            assets.mkdir(exist_ok=True)
                            name = f"{len(list(assets.iterdir())):03}-{target.name}"
                            target = Path(shutil.copyfile(target, assets / name))
                        node["c"][2][0] = target.relative_to(temp).as_posix()
            data = json.dumps(document, ensure_ascii=False)
            command(*common, "--to=typst", "-V", "mainfont=Noto Serif CJK SC",
                    "-V", "monofont=Noto Sans Mono CJK SC", "-o", str(src), stdin=data)
            command("typst", "compile", src.name, pdf.name, cwd=temp)
            files.append(pdf)
        for file in files:
            dest = output / file.name
            file.replace(dest)
            print(dest)


if __name__ == "__main__":
    main()
