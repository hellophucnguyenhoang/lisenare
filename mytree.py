#!/usr/bin/env python3
import os
import sys
from collections import defaultdict


def print_tree(
    path, max_depth=2, max_files_per_ext=3, current_depth=1, prefix=""
):
    try:
        entries = sorted(os.listdir(path))
    except PermissionError:
        return

    # Separate directories and files (ignoring hidden files starting with '.')
    dirs = [
        e
        for e in entries
        if os.path.isdir(os.path.join(path, e)) and not e.startswith(".")
    ]
    files = [
        e
        for e in entries
        if os.path.isfile(os.path.join(path, e)) and not e.startswith(".")
    ]

    # Group files by their extensions
    ext_groups = defaultdict(list)
    for f in files:
        # Get extension (e.g., '.json', '.jpg') or label as 'no_ext' if it doesn't have one
        _, ext = os.path.splitext(f)
        ext = ext.lower() if ext else "no_ext"
        ext_groups[ext].append(f)

    # Build the limited files list and track truncated extensions
    allowed_files = []
    truncated_info = []

    # Sort extensions alphabetically so output is predictable
    for ext in sorted(ext_groups.keys()):
        all_files_in_ext = ext_groups[ext]
        allowed_files.extend(all_files_in_ext[:max_files_per_ext])

        # If there are more files for this extension, log how many were left out
        if len(all_files_in_ext) > max_files_per_ext:
            num_hidden = len(all_files_in_ext) - max_files_per_ext
            ext_label = ext if ext != "no_ext" else "no extension"
            truncated_info.append(f"... ({num_hidden} more {ext_label} files)")

    # Combine directories and allowed files
    display_items = dirs + allowed_files + truncated_info

    for i, item in enumerate(display_items):
        is_last = i == len(display_items) - 1
        connector = "└── " if is_last else "├── "

        print(f"{prefix}{connector}{item}")

        # Recursively explore directories within depth limit
        if item in dirs and current_depth < max_depth:
            next_prefix = prefix + ("    " if is_last else "│   ")
            print_tree(
                os.path.join(path, item),
                max_depth,
                max_files_per_ext,
                current_depth + 1,
                next_prefix,
            )


if __name__ == "__main__":
    # Use current directory unless a path argument is provided
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    print(os.path.basename(os.path.abspath(target_dir)) or target_dir)
    print_tree(target_dir)
