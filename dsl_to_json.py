import sys
from pathlib import Path
from DSL.dsl_to_validated_json import convert_dsl_to_json


def main():
    if len(sys.argv) < 3:
        print("Usage: python dsl_to_json.py input.simdsl output.json [--no-validate]")
        sys.exit(1)

    dsl_path = Path(sys.argv[1])
    json_path = Path(sys.argv[2])

    validate = "--no-validate" not in sys.argv

    convert_dsl_to_json(dsl_path, json_path, validate=validate)


if __name__ == "__main__":
    main()

