def next_commands(event, order):
    if event.get("age", 6) > 5:
        return []
    return [{"type": "forward"}]
