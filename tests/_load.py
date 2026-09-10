"""Laedt die Skripte aus bin/ als Module, obwohl sie keine .py-Endung haben."""
import os, pathlib, sys, types

ROOT = pathlib.Path(__file__).resolve().parent.parent


def load(name, **overrides):
    src = (ROOT / "bin" / name).read_text(encoding="utf-8")
    mod = types.ModuleType(name.replace("-", "_"))
    mod.__dict__["__name__"] = mod.__name__
    mod.__dict__["__file__"] = str(ROOT / "bin" / name)
    exec(compile(src, str(ROOT / "bin" / name), "exec"), mod.__dict__)
    for k, v in overrides.items():
        setattr(mod, k, v)
    return mod
