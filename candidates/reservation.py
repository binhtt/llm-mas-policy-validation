def next_commands(event, order):
    available = event["cash"] - event["reserved"]
    cost = order["price"] * order["qty"]
    if order["qty"] > 10 or cost > available:
        return []
    return [{"type": "approve"}]
