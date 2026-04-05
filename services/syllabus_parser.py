# services/syllabus_parser.py

import re

def parse_syllabus(text):
    """
    Converts raw syllabus text into clean topic list
    """
    lines = text.split("\n")
    topics = []

    for line in lines:
        line = line.strip()
        if len(line) < 4:
            continue

        # remove numbering
        line = re.sub(r"^[0-9.\-()]+", "", line).strip()
        topics.append(line)

    return list(set(topics))  # unique topics