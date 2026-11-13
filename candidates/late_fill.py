def next_commands(event, order):
    if event.get("seen", False):
        return []
    return [{"type": "apply_fill", "qty": event["qty"]}]
