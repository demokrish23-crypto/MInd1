import random
import re
import itertools

BLOOMS = {
    "remember": ["Define", "List", "Identify"],
    "understand": ["Explain", "Describe", "Illustrate"],
    "apply": ["Apply", "Demonstrate", "Solve"],
    "analyze": ["Analyze", "Differentiate", "Compare"],
    "evaluate": ["Evaluate", "Justify", "Assess"],
    "create": ["Design", "Develop", "Construct"]
}

TEMPLATES = {
    2: [
        "{verb} the concept of {topic}.",
        "{verb} {topic} with one example."
    ],
    4: [
        "{verb} the working of {topic}.",
        "{verb} {topic} using a suitable example.",
        "{verb} advantages and limitations of {topic}."
    ],
    8: [
        "{verb} {topic} with algorithm and complexity analysis.",
        "{verb} real-world applications of {topic} and justify.",
        "{verb} {topic} and compare with alternative techniques."
    ]
}

INVALID = re.compile(r"\b(def|return|import|flask|route|uuid|render|request|pdf|docx)\b", re.I)

def clean_topics(text):
    return [t.strip() for t in text.split(",") if t.strip() and not INVALID.search(t)]

def generate_section_questions(subject, syllabus, marks, bloom_levels, count):
    topics = clean_topics(syllabus)
    used = set()
    questions = []

    combos = list(itertools.product(topics, bloom_levels, TEMPLATES[marks]))
    random.shuffle(combos)

    for topic, bloom, template in combos:
        verb = random.choice(BLOOMS[bloom])
        text = template.format(verb=verb, topic=topic)

        sig = f"{topic}-{verb}-{bloom}"
        if sig not in used:
            used.add(sig)
            questions.append({
                "subject": subject,
                "topic": topic,
                "marks": marks,
                "bloom": bloom,
                "text": text
            })

        if len(questions) == count:
            break

    return questions