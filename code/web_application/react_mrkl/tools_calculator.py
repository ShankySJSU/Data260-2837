import ast
import operator
import re
from datetime import datetime, timezone

_WHITELIST = re.compile(r"^[0-9+\-*/().\s]+$")
_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_UN = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _ts():
    return datetime.now(timezone.utc).isoformat()


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UN:
        return _UN[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
        return _BIN[type(node.op)](_eval(node.left), _eval(node.right))
    raise ValueError("Invalid expression")


def calculator(expression: str, units: str = None):
    """Safe arithmetic; whitelist ^[0-9+\\-*/().\\s]+$, no eval."""
    try:
        if not _WHITELIST.match(expression):
            raise ValueError("Expression contains characters outside the whitelist")
        value = _eval(ast.parse(expression.strip(), mode="eval").body)
        data = {"value": value}
        if units:
            data["units"] = units
        return {"success": True, "data": data, "source": "calculator", "ts": _ts()}
    except Exception as e:
        return {"success": False, "error": f"Calculator error: {e}", "source": "calculator", "ts": _ts()}