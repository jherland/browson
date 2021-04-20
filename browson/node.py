from typing import Any, List, Optional


class Node:
    """Encapsulate the tree of a Python (or JSON) data structure."""

    @staticmethod
    def is_scalar(value):
        """Return True iff 'value' should be represented by a leaf node."""
        return not isinstance(value, (dict, list, tuple, set))

    @classmethod
    def build(cls, obj, name="", parent=None, **kwargs):
        if cls.is_scalar(obj):
            return cls(name, type(obj), obj, parent=parent, **kwargs)
        else:
            children = []
            ret = cls(
                name,
                type(obj),
                obj,
                parent=parent,
                _children=children,
                **kwargs,
            )

            if isinstance(obj, dict):
                children.extend(
                    cls.build(v, f"{name}.{k}", parent=ret, key=k)
                    for k, v in obj.items()
                )
            else:
                children.extend(
                    cls.build(v, f"{name}[{i}]", parent=ret)
                    for i, v in enumerate(obj)
                )
            return ret

    def __init__(self, name, kind, value, **kwargs):
        self.name: str = name
        self.kind: type = kind
        self.value: Any = value
        self.parent: "Optional[Node]" = None
        self._children: "Optional[List[Node]]" = None
        self.__dict__.update(kwargs)

    def __str__(self):
        num_children = "*" if self.is_leaf else len(self._children)
        return f"{self.name}/{self.kind.__name__}/{num_children}"

    def __repr__(self):
        args = [f"{k}={v!r}" for k, v in self.__dict__.items()]
        return f"{self.__class__.__name__}({', '.join(args)})"

    def __eq__(self, other):
        assert isinstance(other, Node), repr(other)
        result = self.name == other.name and self.value == other.value
        if result:
            assert self.kind is other.kind, f"{self} != {other}"
        return result

    @property
    def is_leaf(self):
        """Return True iff this is a leaf node (i.e. cannot have any children).

        This is different from an empty container, i.e. an "internal" node
        whose list of children is empty."""
        return self._children is None

    @property
    def children(self):
        """Return this node's children.

        Return an empty list for leaf nodes, as a convenience for callers that
        typically iterated over this methods return value."""
        return [] if self._children is None else self._children

    @property
    def is_child(self):
        return self.parent is not None

    @property
    def is_first_child(self):
        return self.is_child and self is self.parent.children[0]

    @property
    def is_last_child(self):
        return self.is_child and self is self.parent.children[-1]

    @property
    def level(self):
        return 0 if self.parent is None else (self.parent.level + 1)

    @property
    def has_key(self):
        return hasattr(self, "key")

    def ancestors(self, include_self=False):
        """Yield transitive parents of this node."""
        if include_self:
            yield self
        if self.parent is not None:
            yield from self.parent.ancestors(include_self=True)

    def yield_node(node):
        yield node

    def dfwalk(self, preorder=yield_node, postorder=None):
        """Depth-first walk, yields values yielded from visitor function."""
        if preorder is not None:
            yield from preorder(self)
        for child in self.children:
            yield from child.dfwalk(preorder, postorder)
        if postorder is not None:
            yield from postorder(self)
