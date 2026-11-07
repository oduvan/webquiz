"""How a recorded step is shown as text.

This module does not need Playwright, so the checks (and their tests) can use it
on a machine where only the WebQuiz test tools are installed.
"""


def format_step(record):
    """The text an agent gets back for a step."""
    lines = [f"STEP {record['step']}  (time +{record['t']:.1f} s)"]
    lines.append(f"RESULT: {record['result'] or ''}" + (f"  ERROR: {record['error']}" if record.get("error") else ""))
    lines.append("SCREEN:")
    lines.append(record["screen"])
    if record["clickable"]:
        items = [f"[{c['kind']}] {c['label']}" + (" (disabled)" if c["disabled"] else "") for c in record["clickable"]]
        lines.append("CLICKABLE: " + " · ".join(items))
    if record["inputs"]:
        items = [
            f"[{i['kind']}] {i['label']} = \"{i['value']}\"" + (" (disabled)" if i["disabled"] else "")
            for i in record["inputs"]
        ]
        lines.append("TYPE INTO: " + " · ".join(items))
    return "\n".join(lines)
