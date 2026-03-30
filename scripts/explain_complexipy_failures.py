from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class FunctionSignals:
    if_count: int = 0
    loop_count: int = 0
    try_count: int = 0
    match_count: int = 0
    boolop_count: int = 0
    comprehension_count: int = 0


class _SignalVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.signals = FunctionSignals()

    def visit_If(self, node: ast.If) -> Any:
        self.signals.if_count += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> Any:
        self.signals.loop_count += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> Any:
        self.signals.loop_count += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> Any:
        self.signals.loop_count += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> Any:
        self.signals.try_count += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> Any:
        self.signals.match_count += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> Any:
        self.signals.boolop_count += 1
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> Any:
        self.signals.comprehension_count += 1
        self.generic_visit(node)

    def visit_DictComp(self, node: ast.DictComp) -> Any:
        self.signals.comprehension_count += 1
        self.generic_visit(node)

    def visit_SetComp(self, node: ast.SetComp) -> Any:
        self.signals.comprehension_count += 1
        self.generic_visit(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> Any:
        self.signals.comprehension_count += 1
        self.generic_visit(node)


def _find_latest_report() -> Path | None:
    reports = sorted(Path.cwd().glob("complexipy_results_*.json"), key=lambda p: p.stat().st_mtime)
    if not reports:
        return None
    return reports[-1]


def _load_report(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def _build_function_index(module: ast.AST) -> dict[str, tuple[int, FunctionSignals]]:
    index: dict[str, tuple[int, FunctionSignals]] = {}

    def walk(node: ast.AST, class_stack: list[str]) -> None:
        if isinstance(node, ast.ClassDef):
            for class_member in node.body:
                walk(class_member, class_stack + [node.name])
            return

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            key = f"{'::'.join(class_stack)}::{node.name}" if class_stack else node.name

            visitor = _SignalVisitor()
            visitor.visit(node)
            index[key] = (getattr(node, "lineno", 1), visitor.signals)

        for ast_child in ast.iter_child_nodes(node):
            walk(ast_child, class_stack)

    walk(module, [])
    return index


def _format_suggestion(signals: FunctionSignals) -> str:
    candidates: list[str] = []
    if signals.if_count >= 4:
        candidates.append("bryt ut delar av if/elif-grenar till små hjälpfunktioner")
    if signals.loop_count >= 2:
        candidates.append("dela upp loop-logik i separata steg")
    if signals.try_count >= 2:
        candidates.append("minska storleken på try-block och hantera fel närmare källan")
    if signals.boolop_count >= 3:
        candidates.append("förenkla komplexa boolska uttryck med mellanvariabler")
    if signals.comprehension_count >= 2:
        candidates.append("ersätt komplexa comprehensions med tydligare mellan-steg")

    if not candidates:
        return "bryt ut en del av funktionen i 1-2 rena hjälpfunktioner"
    return "; ".join(candidates)


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain complexipy failures with actionable hints.")
    parser.add_argument("--max", type=int, required=True, dest="max_complexity")
    args = parser.parse_args()

    report_path = _find_latest_report()
    if report_path is None:
        print("Ingen complexipy-rapport hittades (complexipy_results_*.json).")
        return 0

    report_items = _load_report(report_path)
    failed_items = [item for item in report_items if int(item.get("complexity", 0)) > args.max_complexity]

    if not failed_items:
        return 0

    print("\nComplexity failure explanation")
    print(f"Rapport: {report_path.name}")
    print(f"Tröskel: {args.max_complexity}\n")

    for item in failed_items:
        path = Path(str(item.get("path", "")))
        function_name = str(item.get("function_name", ""))
        complexity = int(item.get("complexity", 0))
        over_by = complexity - args.max_complexity

        line_no = "?"
        signals = FunctionSignals()
        if path.exists():
            module = ast.parse(path.read_text(encoding="utf-8"))
            index = _build_function_index(module)
            if function_name in index:
                found_line, found_signals = index[function_name]
                line_no = str(found_line)
                signals = found_signals

        print(f"- {path}:{line_no} -> {function_name}")
        print(f"  Orsak: komplexitet {complexity} överskrider gränsen {args.max_complexity} med {over_by}.")
        print(
            "  Struktursignaler: "
            f"if={signals.if_count}, loop={signals.loop_count}, try={signals.try_count}, "
            f"match={signals.match_count}, boolop={signals.boolop_count}, comp={signals.comprehension_count}."
        )
        print(f"  Förslag: {_format_suggestion(signals)}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
