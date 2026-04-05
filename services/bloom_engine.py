# services/bloom_engine.py

import random

BLOOM_TEMPLATES = {
    2: [
        ("Define {topic}.", "Remembering"),
        ("List the key features of {topic}.", "Remembering"),
        ("Identify common use-cases of {topic}.", "Understanding"),
        ("Discuss why {topic} is important.", "Understanding")
    ],

    4: [
        ("Explain {topic} with a suitable example.", "Understanding"),
        ("Demonstrate {topic} in a simple case.", "Applying"),
        ("Apply {topic} to solve a practical problem.", "Applying"),
        ("Analyze a scenario for {topic}.", "Analyzing")
    ],

    8: [
        ("Analyze {topic} in detail with examples.", "Analyzing"),
        ("Design an algorithm or solution using {topic}.", "Creating"),
        ("Evaluate the advantages and limitations of {topic}.", "Evaluating"),
        ("Create a complete architecture/plan for {topic}.", "Creating")
    ]
}

DIFFICULTY_BLOOM_PROFILE = {
    1: {"Remembering": 0.45, "Understanding": 0.30, "Applying": 0.15, "Analyzing": 0.06, "Evaluating": 0.03, "Creating": 0.01},
    2: {"Remembering": 0.35, "Understanding": 0.30, "Applying": 0.20, "Analyzing": 0.10, "Evaluating": 0.04, "Creating": 0.01},
    3: {"Remembering": 0.20, "Understanding": 0.25, "Applying": 0.25, "Analyzing": 0.15, "Evaluating": 0.10, "Creating": 0.05},
    4: {"Remembering": 0.10, "Understanding": 0.20, "Applying": 0.25, "Analyzing": 0.20, "Evaluating": 0.15, "Creating": 0.10},
    5: {"Remembering": 0.05, "Understanding": 0.10, "Applying": 0.20, "Analyzing": 0.25, "Evaluating": 0.20, "Creating": 0.20},
}

MARKS_BLOOM_MAP = {
    2: ["Remembering", "Understanding"],
    4: ["Understanding", "Applying", "Analyzing"],
    8: ["Analyzing", "Evaluating", "Creating"],
}


def _choose_bloom(marks, difficulty):
    allowed = MARKS_BLOOM_MAP.get(marks, list(DIFFICULTY_BLOOM_PROFILE[3].keys()))
    profile = DIFFICULTY_BLOOM_PROFILE.get(difficulty, DIFFICULTY_BLOOM_PROFILE[3])

    weights = [profile.get(bloom, 0) for bloom in allowed]
    total = sum(weights)
    if total <= 0:
        return random.choice(allowed)

    return random.choices(allowed, weights=weights, k=1)[0]


def _build_co_level(topic, index):
    value = (abs(hash(topic)) + index) % 6 + 1
    return f"CO{value}"


def generate_question(topic, marks, used, difficulty=3, index=0):
    templates = BLOOM_TEMPLATES.get(marks, BLOOM_TEMPLATES[2])
    desired_bloom = _choose_bloom(marks, difficulty)

    attempts = 0
    selected_question = None
    selected_bloom = desired_bloom

    while attempts < 30:
        candidates = [t for t in templates if t[1] == desired_bloom]
        if not candidates:
            candidates = templates

        template, bloom_level = random.choice(candidates)
        question_text = template.format(topic=topic)

        if question_text not in used:
            selected_question = question_text
            selected_bloom = bloom_level
            used.add(question_text)
            break

        attempts += 1

    if not selected_question:
        selected_question = f"Discuss {topic} in terms of key ideas, applications, and challenges."
        if selected_question not in used:
            used.add(selected_question)
        selected_bloom = desired_bloom

    co_level = _build_co_level(topic, index)
    return selected_question, selected_bloom, co_level
