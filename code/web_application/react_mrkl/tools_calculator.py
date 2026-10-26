import ast
import operator
from datetime import datetime

def _timestamp():
    return datetime.utcnow().isoformat()

# Allowed operators only
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}

def _eval(node):
    """
    Very small safe expression evaluator (HW7 requirement).
    """
    if isinstance(node, ast.Num):
        return node.n

    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in SAFE_OPERATORS:
            raise ValueError("Operator not allowed")
        return SAFE_OPERATORS_eval(node.operand)

    if isinstance(node, ast.BinOp):
        if type(node.op) not in SAFE_OPERATORS:
            raise ValueError("Operator not allowed")
        return SAFE_OPERATORS_eval(node.left), _eval(node.right)

    raise ValueError("Invalid expression")


def calculator(expression: str, units: str = None):
    """
    Safe arithmetic evaluator.

    HW7 Requirements:
    - Allow numbers + +-*/() only
    - No eval, no variable execution
    """
    try:
        # Parse the expression
        tree = ast.parse(expression, mode="eval")
        value = _eval(tree.body)

        return {
            "success": True,
            "data": {
                "value": value,
                "units": units
            },
            "error": None,
            "source": "calculator",
            "ts": _timestamp()
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Calculator error: {str(e)}",
            "source": "calculator",
            "ts": _timestamp()
        }