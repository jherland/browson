import json
import subprocess
import sys
from tempfile import NamedTemporaryFile
import textwrap


class Test_noninteractive_dump:
    def run_on_json_data(self, data):
        with NamedTemporaryFile(mode="w+") as f:
            json.dump(data, f)
            f.flush()
            proc = subprocess.run(
                [sys.executable, "-m", "browson", f.name],
                stdout=subprocess.PIPE,
                encoding="UTF-8",
                check=True,
            )
            return proc.stdout

    def test_nested_dict(self):
        data = {"foo": {"a": 1, "b": 2}, "bar": {"c": 3, "d": 4}}
        assert self.run_on_json_data(data) == textwrap.dedent(
            """\
            {
              "foo": {
                "a": 1,
                "b": 2
              },
              "bar": {
                "c": 3,
                "d": 4
              }
            }
            """
        )
