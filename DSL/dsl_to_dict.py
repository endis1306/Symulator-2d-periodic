from lark import Lark, Transformer, v_args
import json

DSL_GRAMMAR = r"""
?start: world

world: "world" "{" stmt* "}"

?stmt: assign ";"
     | block_stmt
     | object_def

assign: NAME ":" expr

block_stmt: NAME "{" stmt* "}"

object_def: "object" STRING "{" stmt* "}"

?expr: call
     | list
     | atom

call: NAME "(" [arg_list] ")"
arg_list: arg ("," arg)*
arg: NAME "=" expr

list: "[" [expr ("," expr)*] "]"

block: "{" stmt* "}"

?atom: NUMBER  -> number
     | STRING  -> string
     | BOOLEAN -> boolean

BOOLEAN.10: "true" | "false"

%import common.CNAME -> NAME
%import common.SIGNED_NUMBER -> NUMBER
%import common.ESCAPED_STRING -> STRING

LINE_COMMENT: /(#|\/\/)[^\n]*/

%import common.WS
%ignore WS
%ignore LINE_COMMENT
"""




def normalize_call(val, *, name):
    if "__call__" not in val:
        raise ValueError(f"{name} musi być wywołaniem funkcji")

    return {
        "type": val["__call__"],
        **{k: v for k, v in val.items() if k != "__call__"}
    }





@v_args(inline=True)
class DSLTransformer(Transformer):

    # ---------- TOP LEVEL ----------

    def world(self, *stmts):
        return self._process_block(stmts)

    def object_def(self, name, *stmts):
        obj_id = str(name)[1:-1]
        content = self._process_block(stmts)
        content["id"] = obj_id
        return ("object", content)

    # ---------- STATEMENTS ----------

    def assign(self, name, value):
        return (str(name), value)

    def block(self, *stmts):
        return self._process_block(stmts)

    def block_stmt(self, name, *stmts):
        return (str(name), self._process_block(stmts))

    # ---------- EXPRESSIONS ----------

    def call(self, name, args=None):
        return {
            "__call__": str(name),
            **(args or {})
        }

    def arg_list(self, *args):
        return dict(args)

    def arg(self, name, value):
        return (str(name), value)

    def list(self, *items):
        return [i for i in items if i is not None]

    # ---------- ATOMS ----------

    def number(self, n):
        s = str(n)
        return float(s) if "." in s else int(s)

    def string(self, s):
        return str(s)[1:-1]

    def boolean(self, b):
        return str(b) == "true"

    # ---------- BLOCK PROCESSING ----------

    def _process_block(self, stmts):
        res = {}

        for stmt in stmts:
            if not stmt:
                continue

            key, val = stmt

            if key == "object":
                res.setdefault("objects", []).append(val)

            elif key == "shape":
                shape = normalize_call(val, name="shape")
                res["shape"] = shape

            elif key == "logic":
                logic = normalize_call(val, name="logic")
                res["logic"] = {
                    "type": logic["type"],
                    "params": {k: v for k, v in logic.items() if k != "type"}
                }

            elif key == "engines":
                res["engines"] = [
                    normalize_call(v, name="rotor") for v in (val or [])
                ]

            elif key == "sensors":
                res["sensors"] = [
                    normalize_call(v, name="sensor") for v in (val or [])
                ]

            else:
                res[key] = val

        return res


def dsl_to_dict(text: str) -> dict:
    parser = Lark(
        DSL_GRAMMAR,
        parser="lalr",
        propagate_positions=True
    )
    tree = parser.parse(text)
    return DSLTransformer().transform(tree)


if __name__ == "__main__":
    example_dsl = """
    world {
  delta_t: 0.01;
  iterations: 1000;

  object "obj1" {

    static: false;

    bodyParams {
      mass: 1.0;
      I: 0.5;
    }
  }

}
    """
    print(json.dumps(dsl_to_dict(example_dsl), indent=2))