class Node:
    """Encapsulate the tree of a Python (or JSON) data structure."""

    @staticmethod
    def is_scalar(obj):
        return not isinstance(obj, (dict, list, tuple, set))

    @classmethod
    def build(cls, obj, name="", level=0, **kwargs):
        if cls.is_scalar(obj):
            return cls(name, type(obj), obj, level=level, **kwargs)
        else:
            child_args = dict(level=level + 1, is_child=True)
            if isinstance(obj, dict):
                children = [
                    cls.build(v, f"{name}.{k}", key=k, **child_args)
                    for k, v in obj.items()
                ]
            else:
                children = [
                    cls.build(v, f"{name}[{i}]", **child_args)
                    for i, v in enumerate(obj)
                ]
            if children:
                children[0]["is_first_child"] = True
                children[-1]["is_last_child"] = True
            return cls(
                name, type(obj), obj, level=level, children=children, **kwargs
            )

    def __init__(self, name, kind, value, **kwargs):
        self.name = name
        self.kind = kind
        self.value = value
        self.extra = kwargs

    def __contains__(self, key):
        return key in self.extra

    def get(self, key, default=None):
        return self.extra.get(key, default)

    def __getitem__(self, key):
        return self.extra[key]

    def __setitem__(self, key, value):
        self.extra[key] = value

    def __delitem__(self, key):
        del self.extra[key]

    @property
    def key(self):
        """Dict items have a key associated with their value."""
        return self["key"]

    @property
    def is_leaf(self):
        """Return True iff this node does not have any children."""
        return "children" not in self.extra

    # TODO: @property
    def children(self, default=None):
        """Internal nodes (aka. collections) have children nodes."""
        return self.get("children", default)

    def __str__(self):
        children = self.children()
        num_children = "*" if children is None else len(children)
        return f"{self.name}/{self.kind.__name__}/{num_children}"

    def __repr__(self):
        args = [repr(self.name), self.kind.__name__, repr(self.value)]
        args += [f"{k}={v!r}" for k, v in self.extra.items()]
        return f"{self.__class__.__name__}({', '.join(args)})"

    def __eq__(self, other):
        assert isinstance(other, Node), repr(other)
        result = self.name == other.name and self.value == other.value
        assert self.kind is other.kind
        return result

    def yield_node(node):
        yield node

    def dfwalk(self, preorder=yield_node, postorder=None):
        """Depth-first walk, yields values yielded from visitor function."""
        if preorder is not None:
            yield from preorder(self)
        for child in self.children(()):
            yield from child.dfwalk(preorder, postorder)
        if postorder is not None:
            yield from postorder(self)
