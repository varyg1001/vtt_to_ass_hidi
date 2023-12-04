#!/usr/bin/env python3

import argparse
import sys
import re
from copy import deepcopy
from pathlib import Path

from pysubs2 import SSAFile, SSAEvent, SSAStyle

parser = argparse.ArgumentParser(description="hidi subtitle converter")
parser.add_argument("path", type=Path, nargs="*", default=None, help="Input file.")
parser.add_argument(
    "-c",
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

COLORS = {
    "white": "FFFF",
    "yellow": "FFFFFF",
    "FFFFFF": "FFFF",
}

resy: int = 360
resx: int = 640


def get_mill(time: str) -> int:
    """
    Converts a time string in the format 'HH:MM:SS.sss' to milliseconds.
    """
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
    formatting = list()
    names = list()
    sub = SSAFile()
    styles = set()

    # styles
    sub.styles["Default"].shadow = 0
    sub.styles["Default"].outline = 1
    sub.styles["Default"].fontsize = 25
    sub.styles["Top"] = sub.styles["Default"].copy()
    sub.styles["Top"].alignment = SSAStyle.alignment.TOP_CENTER

    if styles := re.findall(r"<c.(.*)-C[0-9]+_[1-9]", path.read_text()):
        styles = set(styles)

    with open(path) as f:
        lines = f.readlines()
        for x in styles:
            if "Subtitle" not in x:
                sub.styles[x] = sub.styles["Default"].copy()

        if "Caption" in styles:
            sub.styles["Caption"].shadow = 0.5

        for x, line in enumerate(lines):
            if line.startswith(tuple(styles)):
                names.append(line.strip())
                temp = lines[x + 1].split(" ")
                data = re.search(r"<c.*>(.+?)</c.*>", lines[x + 2]).group(1)
                event = SSAEvent(text=data)

                if line.startswith("Song"):
                    event.style = "Song"
                if line.startswith("Caption"):
                    position = re.search(r"position:(\d+)", lines[x + 1]).group(1) or 0
                    line = re.search(r"line:(\d+)", lines[x + 1]).group(1) or 0
                    event.text = f"{{\\an7\\pos({round(resy*float(position) / 100, 2)},{round(resx*float(line) / 100, 2)})}}{event.text}"
                    event.style = "Caption"
                else:
                    if line := re.search(r"line:(\d+)", lines[x + 1]):
                        line = line.group(1)
                        if int(line) < 71:
                            event.style = "Top"

                sub.append(event)
                event.start = get_mill(temp[0])
                event.end = get_mill(temp[2])

    if args.css_file:
        with open(args.css_file) as f:
            css = f.readlines()
        for x in css:
            if (x := x.strip().strip(" .").strip(".")) and any(
                y for y in styles if y in x
            ):
                # remove unnecessary things
                remove = [
                    ".rmp-container>",
                    "rmp-container>",
                    ".rmp-content>.",
                    "rmp-cc-area>",
                    ".rmp-cc-container>",
                    ".rmp-cc-display>",
                    ".rmp-cc-cue",
                ]
                for y in remove:
                    x = x.replace(y, "")
                data = x.strip().replace(", ", "||").split("||")
                if (temp := data[-1].split("{")) and len(temp) == 2:
                    data[-1] = temp[0]
                    data.append(temp[-1].split(";"))
                formatting.append(data)

    for x in formatting:
        add = ""
        font = [y for y in x[-1] if "font-family" in y]
        size = [y.strip(" font-size:") for y in x[-1] if "font-size" in y]
        color = [y.strip(" color:").strip("#") for y in x[-1] if "color" in y]

        if size and (size := size[0].replace(".", "0.").strip("em")) and size != "1":
            add += f"\\fs{size}"
        if font and (font := font[0].split(",")[-1].strip('"')) and font != "Arial":
            add += f"\\fn{font}"
        if (
            color
            and (color := color[0].strip(";"))
            and color != "yellow"
            and color != "FFFFFF"
        ):
            add += f"\\c&H{COLORS.get(color, color)}&"

        if add:
            for y in x[:-1]:
                y = y.strip(".")
                if y in names:
                    line = sub[names.index(y)]
                    if "}" in line.text:
                        temp = line.text.split("}")
                        temp[0] += add
                        line.text = "}".join(temp)
                    else:
                        line.text = "{" + add + "}" + line.text
                    if "fs" in line.text:
                        size_ = sub.styles[line.style].fontsize
                        line.text = line.text.replace(
                            f"fs{size}",
                            f"fs{int(size_*float(size))}",
                        )

    # new SSAFile for merged lines
    sub_formatted = deepcopy(sub)
    sub_formatted.clear()
    skip: bool = False
    for s, x in enumerate(sub):
        if names[s][-1] != "1":
            if sub[s - 1].style == x.style:
                color = (
                    "{\\c&HFFFFFF&}"
                    if "c&HFFFF&" in sub[s - 1].text and "{" not in x.text
                    else ""
                )
                sub[s - 1].text += f"\\N{color}{x.text}"
                s += 1
                skip = True
        if skip:
            skip = False
        else:
            sub_formatted.append(x)

    path = path.with_suffix(".ass")
    sub_formatted.info["PlayResX"] = str(resx)
    sub_formatted.info["PlayResY"] = str(resy)
    sub_formatted.info["YCbCr Matrix"] = "TV.709"

    sub_formatted.save(path)
