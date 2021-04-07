import json
import subprocess
import sys
from tempfile import NamedTemporaryFile
import textwrap

import browson
from browson import render_nodes
from node import Node
from style import PythonStyle, JSONStyle


class Test_render_nodes_python:
    style = PythonStyle()

    def test_leaf_node(self):
        n = Node.build("foo")
        lines, _ = zip(*render_nodes(n, self.style))
        assert "\n".join(lines) == repr("foo")

    def test_simple_list(self):
        n = Node.build(["foo", 123, True])
        lines, _ = zip(*render_nodes(n, self.style))
        assert "\n".join(lines) == textwrap.dedent(
            """\
            [
                'foo',
                123,
                True,
            ]"""
        )

    def test_simple_dict(self):
        n = Node.build({"foo": 123, "bar": 456, "baz": 789})
        lines, _ = zip(*render_nodes(n, self.style))
        assert "\n".join(lines) == textwrap.dedent(
            """\
            {
                'foo': 123,
                'bar': 456,
                'baz': 789,
            }"""
        )

    def test_nested_dict(self):
        n = Node.build({"foo": {"a": 1, "b": 2}, "bar": {"c": 3, "d": 4}})
        lines, _ = zip(*render_nodes(n, self.style))
        assert "\n".join(lines) == textwrap.dedent(
            """\
            {
                'foo': {
                    'a': 1,
                    'b': 2,
                },
                'bar': {
                    'c': 3,
                    'd': 4,
                },
            }"""
        )


class Test_render_nodes_json:
    style = JSONStyle()

    def test_leaf_node(self):
        n = Node.build("foo")
        lines, _ = zip(*render_nodes(n, self.style))
        assert "\n".join(lines) == '"foo"'

    def test_simple_list(self):
        n = Node.build(["foo", 123, True, False, None])
        lines, _ = zip(*render_nodes(n, self.style))
        assert "\n".join(lines) == textwrap.dedent(
            """\
            [
              "foo",
              123,
              true,
              false,
              null
            ]"""
        )

    def test_simple_dict(self):
        n = Node.build({"foo": 123, "bar": 456, "baz": 789})
        lines, _ = zip(*render_nodes(n, self.style))
        assert "\n".join(lines) == textwrap.dedent(
            """\
            {
              "foo": 123,
              "bar": 456,
              "baz": 789
            }"""
        )

    def test_nested_dict(self):
        n = Node.build({"foo": {"a": 1, "b": 2}, "bar": {"c": 3, "d": 4}})
        lines, _ = zip(*render_nodes(n, self.style))
        assert "\n".join(lines) == textwrap.dedent(
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
            }"""
        )


class Test_noninteractive_dump:
    def run_on_json_data(self, data):
        with NamedTemporaryFile(mode="w+") as f:
            json.dump(data, f)
            f.flush()
            proc = subprocess.run(
                [sys.executable, browson.__file__, f.name],
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
