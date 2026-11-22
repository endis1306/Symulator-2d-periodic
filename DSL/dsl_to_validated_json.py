import json
from pathlib import Path
from pydantic import ValidationError

from DSL.dsl_to_dict import dsl_to_dict
from DSL.configs import WorldConfig


def convert_dsl_to_json(
    dsl_path: Path,
    json_path: Path,
    validate: bool = True
):
    raw_dict = dsl_to_dict(dsl_path.read_text(encoding="utf-8"))

    if validate:
        try:
            config = WorldConfig.model_validate(raw_dict)
        except ValidationError as e:
            print("\n❌ BŁĄD WALIDACJI CONFIGA\n")
            print(e)
            raise SystemExit(1)

        data = config.model_dump()
    else:
        data = raw_dict

    json_path.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8"
    )

    print(f"✔ DSL → JSON OK: {json_path}")

