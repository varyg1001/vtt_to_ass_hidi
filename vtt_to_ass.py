#!/usr/bin/env python3

import argparse
import sys
import re
from pathlib import Path

import ass
from pysubs2 import SSAFile, SSAEvent

parser = argparse.ArgumentParser(description="hidi subtitle converter")
parser.add_argument("path", type=Path, nargs="*", default=None, help="Input file.")
parser.add_argument(
    "-css",
    "--css-file",
    type=Path,
    default=None,
    help="css file for formatting",
)
args = parser.parse_args()

if len(sys.argv) == 1 or args.path is None:
    parser.print_help(sys.stderr)
    sys.exit(1)

if args.css_file and len(args.path) > 2:
    print("If css file if provided, only one file can be converted at a time.")
    sys.exit(1)


def get_milliseconds(time: str):
    temp1 = time.split(".")
    temp = temp1[0].split(":")
    milliseconds = (
        (int(temp[0]) * 3600000)
        + (int(temp[1]) * 60000)
        + (int(temp[2]) * 1000)
        + int(temp1[1])
    )
    return milliseconds


for path in args.path:
    sub = SSAFile()
    with open(path) as f:
        lines = f.readlines()
        for x, line in enumerate(lines):
            if line.startswith("Caption-") or line.startswith("Subtitle-"):
                temp = lines[x + 1].split(" ")
                data = re.search(r"<c.*>(.+?)</c.*>", lines[x + 2]).group(1)
                event = SSAEvent(text=data)
                if line.startswith("Caption-"):
                    position = re.search(r"position:(\d+)", lines[x + 1]).group(1) or 0
                    line = re.search(r"line:(\d+)", lines[x + 1]).group(1) or 0
                    event.text = f"{{\\an7\\pos({round(640*float(position) / 100, 2)},{round(360*float(line) / 100, 2)})}}{event.text}"
                    event.style = "Caption"
                sub.append(event)
                event.start = get_milliseconds(temp[0])
                event.end = get_milliseconds(temp[2])

    for x in sub:
        print(x)

    if args.css_file:
        with open(args.css_file) as f:
            css = f.readlines()
        for x in css:
            if (x := x.strip().strip(" .")) and ("Caption" in x or "Subtitle" in x):
                data = x.replace("rmp-container>.rmp-content>.rmp-cc-area>.rmp-cc-container>.rmp-cc-display>.rmp-cc-cue", "")
                print(data.strip().replace(",. ", "||").split("||"))

    sub_formatted = SSAFile()
    # create new styles
    sub.styles["Default"].shadow = 0
    sub.styles["Default"].outline = 1
    sub.styles["Default"].fontsize = 25
    sub.styles["Caption"] = sub.styles["Default"].copy()
    sub.styles["Caption"].shadow = 0.3
    sub.styles["Caption"].outline = 0.8
    sub.styles["Caption"].fontsize = 20

    path = path.with_suffix(".ass")
    sub.save(path)

    with open(path, encoding="utf_8_sig") as f:
        doc = ass.parse(f)
    doc.info["PlayResX"] = 640
    doc.info["PlayResY"] = 360
    with open(path, "w", encoding="utf_8_sig") as f:
        doc.dump_file(f)
