from datetime import date
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .models import Result, Session
from .report import render_report

PROMPTS = {
    "role": "What target role or opportunity are you preparing for?",
    "background": "What is your experience and which skills do you self-report?",
    "deadline": "What is your preparation deadline? Use YYYY-MM-DD.",
    "description": "Paste the opportunity/job description in one message, or type skip.",
}


def current_prompt(s):
    if s.stage in PROMPTS:
        return PROMPTS[s.stage]
    if s.stage == "complete":
        return s.report or "Assessment complete."
    return s.assessment.questions[s.index].display_prompt(s.follow_up)


class Turn(TypedDict):
    session: Session
    text: str
    reply: str


def build_graph(ai):
    def intake(t):
        s, text = t["session"], t["text"]
        if s.stage == "deadline":
            try:
                deadline = date.fromisoformat(text)
                if deadline < date.today():
                    raise ValueError()
            except ValueError:
                return {"reply": "Please enter a deadline today or later in YYYY-MM-DD format."}
        key = s.stage
        s.profile[key] = text
        stages = list(PROMPTS)
        if key == "description":
            s.assessment = ai.analyze(s.profile)
            s.stage = "assessment"
            return {
                "reply": "Requirements to explore:\n"
                + "\n".join(f"- {r}" for r in s.assessment.requirements)
                + "\n\n"
                + current_prompt(s)
            }
        s.stage = stages[stages.index(key) + 1]
        return {"reply": current_prompt(s)}

    def assess(t):
        s, text = t["session"], t["text"]
        q = s.assessment.questions[s.index]
        answers = [s.pending_answer, text] if s.pending_answer is not None else [text]
        e = ai.evaluate(q, answers, s.follow_up)
        if e.follow_up and s.pending_answer is None:
            s.pending_answer, s.follow_up = text, e.follow_up
            return {"reply": f"Feedback: {e.feedback}\n\n{current_prompt(s)}"}
        e.follow_up = None
        s.results.append(Result(question=q, answers=answers, evaluation=e))
        s.pending_answer, s.follow_up = None, None
        s.index += 1
        feedback = f"{q.skill}: {e.score}/3. {e.feedback}"
        if s.index == len(s.assessment.questions):
            s.stage = "complete"
            s.report = render_report(s)
            return {"reply": feedback + "\n\n" + s.report}
        return {"reply": feedback + "\n\n" + current_prompt(s)}

    graph = StateGraph(Turn)
    graph.add_node("intake", intake)
    graph.add_node("assess", assess)
    graph.add_node(
        "finished", lambda t: {"reply": "Assessment complete. Use /report, /history or /new."}
    )
    graph.add_conditional_edges(
        START,
        lambda t: (
            "assess"
            if t["session"].stage == "assessment"
            else "finished"
            if t["session"].stage == "complete"
            else "intake"
        ),
    )
    for node in ("intake", "assess", "finished"):
        graph.add_edge(node, END)
    return graph.compile()
