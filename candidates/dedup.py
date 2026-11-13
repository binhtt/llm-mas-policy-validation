def next_commands(event, order):
    if not event["seen"]:
        return [{"type": "apply_fill", "qty": event["qty"]}]
    return []
