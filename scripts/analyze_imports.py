#!/usr/bin/env python3
"""Analyze import structure of the codebase to understand dependency complexity."""

import ast
from collections import defaultdict
from pathlib import Path


def find_python_files(root: Path, exclude_dirs: set[str] = None) -> list[Path]:
    """Find all Python files, excluding specified directories."""
    if exclude_dirs is None:
        exclude_dirs = {"__pycache__", ".venv", ".venv312", "venv", ".uv-cache", "node_modules", ".git", "examples"}

    python_files = []
    for path in root.rglob("*.py"):
        if not any(excluded in path.parts for excluded in exclude_dirs):
            python_files.append(path)
    return sorted(python_files)


def get_imports(file_path: Path) -> tuple[list[str], list[str]]:
    """Extract imports from a Python file.

    Returns:
        Tuple of (absolute_imports, relative_imports)
    """
    try:
        with open(file_path) as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return [], []

    absolute_imports = []
    relative_imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                absolute_imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level > 0:  # Relative import
                relative_imports.append(("." * node.level) + module)
            else:
                absolute_imports.append(module)

    return absolute_imports, relative_imports


def identify_local_imports(imports: list[str], project_modules: set[str]) -> list[str]:
    """Filter imports to only include local project imports."""
    local = []
    for imp in imports:
        # Check if it's a project module
        top_level = imp.split(".")[0]
        if top_level in project_modules:
            local.append(imp)
    return local


def compute_transitive_closure(
    file_path: Path,
    import_graph: dict[Path, set[Path]],
    cache: dict[Path, set[Path]] = None
) -> set[Path]:
    """Compute all transitive dependencies for a file."""
    if cache is None:
        cache = {}

    if file_path in cache:
        return cache[file_path]

    # Mark as in-progress to handle cycles
    cache[file_path] = set()

    closure = set()
    for dep in import_graph.get(file_path, set()):
        closure.add(dep)
        closure.update(compute_transitive_closure(dep, import_graph, cache))

    cache[file_path] = closure
    return closure


def main():
    root = Path(__file__).parent.parent

    print(f"Analyzing imports in: {root}\n")

    # Find all Python files
    python_files = find_python_files(root)
    print(f"Found {len(python_files)} Python files\n")

    # Determine project modules (top-level directories with __init__.py)
    project_modules = set()
    for item in root.iterdir():
        if item.is_dir() and (item / "__init__.py").exists():
            project_modules.add(item.name)

    # Also check if root itself is a module
    if (root / "__init__.py").exists():
        project_modules.add(root.name)

    print(f"Project modules: {project_modules}\n")

    # Analyze each file
    file_imports = {}
    all_local_imports = defaultdict(list)

    for file_path in python_files:
        abs_imports, rel_imports = get_imports(file_path)
        local_abs = identify_local_imports(abs_imports, project_modules)

        file_imports[file_path] = {
            "absolute": abs_imports,
            "relative": rel_imports,
            "local_absolute": local_abs,
        }

        total_local = len(local_abs) + len(rel_imports)
        all_local_imports[total_local].append(file_path)

    # Build import graph (file -> set of files it imports)
    import_graph: dict[Path, set[Path]] = defaultdict(set)

    # Create module to file mapping
    module_to_file = {}
    for f in python_files:
        rel_path = f.relative_to(root)
        # Convert path to module name
        if f.name == "__init__.py":
            module_name = ".".join(rel_path.parent.parts)
        else:
            module_name = ".".join(rel_path.with_suffix("").parts)
        if module_name:
            module_to_file[module_name] = f

    # Resolve imports to actual files
    for file_path in python_files:
        info = file_imports[file_path]

        for imp in info["local_absolute"]:
            # Try exact match or as package
            if imp in module_to_file:
                import_graph[file_path].add(module_to_file[imp])
            # Try parent module
            parts = imp.split(".")
            for i in range(len(parts), 0, -1):
                partial = ".".join(parts[:i])
                if partial in module_to_file:
                    import_graph[file_path].add(module_to_file[partial])
                    break

    # Compute transitive closures
    closure_cache = {}
    closures = {}
    for file_path in python_files:
        closures[file_path] = compute_transitive_closure(file_path, import_graph, closure_cache)

    # Statistics
    print("=" * 60)
    print("IMPORT STATISTICS")
    print("=" * 60)

    local_counts = []
    for file_path in python_files:
        info = file_imports[file_path]
        count = len(info["local_absolute"]) + len(info["relative"])
        local_counts.append((count, file_path))

    local_counts.sort(reverse=True)

    print(f"\nTotal files: {len(python_files)}")
    print(f"Average local imports per file: {sum(c for c, _ in local_counts) / len(local_counts):.1f}")
    print(f"Maximum local imports in a file: {local_counts[0][0] if local_counts else 0}")

    print("\n" + "-" * 60)
    print("FILES WITH MOST LOCAL IMPORTS (top 10)")
    print("-" * 60)
    for count, path in local_counts[:10]:
        rel_path = path.relative_to(root)
        print(f"  {count:3d} imports: {rel_path}")

    # Transitive closure sizes
    closure_sizes = [(len(closures[f]), f) for f in python_files]
    closure_sizes.sort(reverse=True)

    print("\n" + "-" * 60)
    print("TRANSITIVE CLOSURE SIZES (top 10)")
    print("-" * 60)
    print("(Number of files needed to load a file with all its dependencies)")
    for size, path in closure_sizes[:10]:
        rel_path = path.relative_to(root)
        print(f"  {size:3d} files: {rel_path}")

    avg_closure = sum(s for s, _ in closure_sizes) / len(closure_sizes) if closure_sizes else 0
    max_closure = closure_sizes[0][0] if closure_sizes else 0

    print(f"\nAverage closure size: {avg_closure:.1f} files")
    print(f"Maximum closure size: {max_closure} files")

    # Practical assessment
    print("\n" + "=" * 60)
    print("PRACTICAL ASSESSMENT")
    print("=" * 60)

    if max_closure <= 5:
        print("✓ Loading files with imports is very practical.")
        print("  Most files have few dependencies.")
    elif max_closure <= 15:
        print("⚠ Loading files with imports is somewhat practical.")
        print("  Some files have moderate dependency chains.")
    else:
        print("✗ Loading files with imports may be impractical.")
        print("  Large dependency chains exist.")

    print(f"\n  Worst case: loading 1 file requires loading {max_closure} additional files")
    print(f"  Average case: loading 1 file requires loading {avg_closure:.1f} additional files")


if __name__ == "__main__":
    main()
