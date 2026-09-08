import json, os, re, time
from dataclasses import dataclass, field
from typing import Any, Dict
from google import genai
from google.genai import types

DEFAULT_MODEL = 'gemini-3.6-flash'
DEPRECATED_MODELS = {'gemini-2.5-flash'}

PLANNING = '''Create a personalized study plan for this student. Return ONLY JSON with: goal, learning_objectives (list), priority_topics (list of objects with topic, priority, reason), study_sequence (list), time_allocation (list of objects with topic, minutes), prerequisites (list), strategy (list). Student profile: {profile}'''
CONTENT = '''Generate accurate, clear study notes using ONLY the approved plan. Return ONLY JSON with: overview, topic_notes (objects with topic, explanation, key_points, key_terms, common_mistakes), cheat_sheet, exam_tips. Profile: {profile} Plan: {plan}'''
ASSESSMENT = '''Create an assessment using ONLY the plan and content. Return ONLY JSON with: flashcards (question, answer), mcqs (question, options, correct_answer, explanation), short_questions (question, answer_points). Include recall, understanding and application. Plan: {plan} Content: {content}'''
REVIEW = '''Strictly audit this study pack. Return ONLY JSON with integer scores 0-100 for overall_score, coverage_score, accuracy_score, difficulty_score, assessment_score, feasibility_score, plus issues (list), recommended_fixes (list), approval (Approved or Needs Refinement). Plan: {plan} Content: {content} Assessment: {assessment}'''
REFINEMENT = '''Create the final improved study pack by applying the review. Return ONLY JSON with title, study_strategy, overview, topic_notes, cheat_sheet, flashcards, mcqs, short_questions, exam_tips. Profile: {profile} Plan: {plan} Content: {content} Assessment: {assessment} Review: {review}'''

class WorkflowError(Exception):
    pass

@dataclass
class WorkflowContext:
    student_profile: Dict[str, Any]
    plan: Dict[str, Any] = field(default_factory=dict)
    content: Dict[str, Any] = field(default_factory=dict)
    assessment: Dict[str, Any] = field(default_factory=dict)
    review: Dict[str, Any] = field(default_factory=dict)
    final_pack: Dict[str, Any] = field(default_factory=dict)


def get_api_key():
    try:
        import streamlit as st
        key = st.secrets.get('GEMINI_API_KEY', '')
        if key: return str(key)
    except Exception:
        pass
    return os.getenv('GEMINI_API_KEY', '').strip()


def get_model():
    """Return a currently supported Gemini model.

    Older deployments may still have GEMINI_MODEL=gemini-2.5-flash
    in Streamlit Secrets, so that value is automatically upgraded.
    """
    model = ''
    try:
        import streamlit as st
        model = str(st.secrets.get('GEMINI_MODEL', '')).strip()
    except Exception:
        pass

    if not model:
        model = os.getenv('GEMINI_MODEL', '').strip()

    if not model or model in DEPRECATED_MODELS:
        return DEFAULT_MODEL

    return model


def parse_json(text):
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', (text or '').strip(), flags=re.I)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, flags=re.S)
        if not match: raise WorkflowError('Gemini returned invalid JSON.')
        try: data = json.loads(match.group(0))
        except json.JSONDecodeError as e: raise WorkflowError(f'Invalid JSON from Gemini: {e}')
    if not isinstance(data, dict): raise WorkflowError('Gemini response must be a JSON object.')
    return data


def call_ai(client, prompt, retries=2):
    last = None
    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model=get_model(), contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3, response_mime_type='application/json')
            )
            return parse_json(getattr(response, 'text', ''))
        except Exception as e:
            last = e
            if attempt < retries: time.sleep(1.5 * (attempt + 1))
    raise WorkflowError(f'Gemini API error: {last}')


def generate_workflow(profile):
    key = get_api_key()
    if not key: raise WorkflowError('GEMINI_API_KEY is missing. Add it to Streamlit Secrets.')
    client = genai.Client(api_key=key)
    c = WorkflowContext(profile)
    c.plan = call_ai(client, PLANNING.format(profile=json.dumps(profile, indent=2)))
    c.content = call_ai(client, CONTENT.format(profile=json.dumps(profile, indent=2), plan=json.dumps(c.plan, indent=2)))
    c.assessment = call_ai(client, ASSESSMENT.format(plan=json.dumps(c.plan, indent=2), content=json.dumps(c.content, indent=2)))
    c.review = call_ai(client, REVIEW.format(plan=json.dumps(c.plan, indent=2), content=json.dumps(c.content, indent=2), assessment=json.dumps(c.assessment, indent=2)))
    c.final_pack = call_ai(client, REFINEMENT.format(profile=json.dumps(profile, indent=2), plan=json.dumps(c.plan, indent=2), content=json.dumps(c.content, indent=2), assessment=json.dumps(c.assessment, indent=2), review=json.dumps(c.review, indent=2)))
    return c


def markdown_pack(c):
    p = c.final_pack
    lines = [f"# {p.get('title','AI Study Pack')}", '', '## Overview', p.get('overview',''), '', '## Study Strategy']
    lines += [f'- {x}' for x in p.get('study_strategy', [])] + ['', '## Topic Notes']
    for t in p.get('topic_notes', []):
        lines += [f"### {t.get('topic','Topic')}", t.get('explanation',''), '', '**Key Points**']
        lines += [f'- {x}' for x in t.get('key_points', [])] + ['', '**Key Terms**']
        lines += [f'- {x}' for x in t.get('key_terms', [])] + ['', '**Common Mistakes**']
        lines += [f'- {x}' for x in t.get('common_mistakes', [])] + ['']
    lines += ['## Cheat Sheet'] + [f'- {x}' for x in p.get('cheat_sheet', [])] + ['', '## Flashcards']
    for i, x in enumerate(p.get('flashcards', []), 1): lines += [f'**{i}. Q:** {x.get("question","")}', f'**A:** {x.get("answer","")}', '']
    lines += ['## MCQs']
    for i, x in enumerate(p.get('mcqs', []), 1):
        lines += [f'**{i}. {x.get("question","")}**'] + [f'- {o}' for o in x.get('options', [])] + [f'**Correct answer:** {x.get("correct_answer","")}', f'**Explanation:** {x.get("explanation","")}', '']
    lines += ['## Short Questions']
    for i, x in enumerate(p.get('short_questions', []), 1): lines += [f'**{i}. {x.get("question","")}**', ', '.join(x.get('answer_points', [])), '']
    lines += ['## Exam Tips'] + [f'- {x}' for x in p.get('exam_tips', [])]
    return '\n'.join(lines)
