def next_commands(event, order):
    if event["seen"]:
        return []
    executed_quantity = event["qty"]
    return [{"type": "apply_fill", "qty": executed_quantity}]
