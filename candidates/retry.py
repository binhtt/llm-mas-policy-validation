def next_commands(event, order):
    if event["kind"] not in ("submit", "timeout"):
        return []
    if not order["approved"] or order["status"] != "approved":
        return []
    return [{"type": "submit", "client_order_id": order["order_id"],
             "price": order["price"], "qty": order["qty"]}]
