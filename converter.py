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
    "-r",
    "--remove-bumper",
    action="store_true",
    help="remove long intro time from time",
)
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
    "HFFFF00": "FFFF",
}

res_x: int = 640
res_y: int = 360


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
    styles = set()
    sub = SSAFile()

    # styles
    sub.styles["Default"].shadow = 0
    sub.styles["Default"].outline = 1
    sub.styles["Default"].fontsize = 22
    sub.styles["Top"] = sub.styles["Default"].copy()
    sub.styles["Top"].alignment = SSAStyle.alignment.TOP_CENTER
    sub.styles["Top"].fontsize = 20

    # get all styles
    if styles := re.findall(r"<c.(.*)-C[0-9]+_[1-9]", path.read_text()):
        styles = set(styles)

    with open(path) as f:
        lines = f.readlines()
    for x in styles:
        if "Subtitle" not in x:
            sub.styles[x] = sub.styles["Default"].copy()

    if "Caption" in styles:
        sub.styles["Caption"].shadow = 0.5
    elif "Song" in styles:
        sub.styles["Song"].fontsize = 20

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
                ry = round(res_y * float(line) / 100, 2)
                rx = round(res_x * float(position) / 100, 2)
                event.text = f"{{\\an7\\pos({rx},{ry})}}{event.text}"
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

    # filter and add formatting from css file
    for x in formatting:
        add = ""
        font = [y for y in x[-1] if "font-family" in y]
        size = [y.strip(" font-size:") for y in x[-1] if "font-size" in y]
        color = [y.strip(" color:").strip("#") for y in x[-1] if "color" in y]
        fontstyle = [y.strip(" font-style:") for y in x[-1] if "font-style" in y]
        if fontstyle and "italic" in fontstyle[0].lower():
            add += f"\\i1"
        elif fontstyle:
            print(f"Unknown fontsyle: {fontstyle}")
        if size and (size := size[0].replace(".", "0.").strip("em")) and size != "1":
            add += f"\\fs{size}"
        if font and (font := font[0].split(",")[-1].strip('"')) and font != "Arial":
            add += f"\\fn{font}"
        if (
            color
            and (color := color[0].strip(";"))
            and color != "yellow"
            and color != "FFFFFF"
            and "font-style:italic" not in x
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
                            f"fs{int(size_ * float(size))}",
                        )

    # new SSAFile for merged lines
    sub_formatted = deepcopy(sub)
    sub_formatted.clear()

    # merge lines
    skip: bool = False
    for s, x in enumerate(sub):
        if names[s][-1] != "1":
            if sub[s - 1].style == x.style:
                color = (
                    "{\\c&HFFFFFF&}"
                    if "c&HFFFF&" in sub[s - 1].text and "{" not in x.text
                    else ""
                )
                if "}" in x.text:
                    sec = x.text.split("}")
                    sec_ = sec[0].strip("{\\").split("\\")
                    sec_ = [
                        y
                        for y in sec_
                        if ("pos" not in y) and (y not in sub[s - 1].text)
                    ]
                    if sec_:
                        x.text = "{" + "\\" + "\\".join(sec_) + "}" + sec[-1]
                    else:
                        x.text = sec[-1]
                sub[s - 1].text += f"\\N{color}{x.text}"
                s += 1
                skip = True
        if skip:
            skip = False
        else:
            sub_formatted.append(x)

    # set infos
    sub_formatted.info["PlayResX"] = str(res_x)
    sub_formatted.info["PlayResY"] = str(res_y)
    sub_formatted.info["YCbCr Matrix"] = "TV.709"

    if args.remove_bumper:
        b_time = get_mill("00:00:04.963")
        for line in sub_formatted:
            line.start -= b_time
            line.end -= b_time

    sub_formatted.save(path.with_suffix(".ass"))
