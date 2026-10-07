"""Token cost comparison: Pocket FDE (curated knowledge) vs raw code context.
No model calls. Just counts tokens in the repo and shows the overhead."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Rough token estimate: ~4 chars per token (Claude's average)
def estimate_tokens(text):
    return max(1, len(text) // 4)


def scan_dir(path, pattern="*", ignore=(".pyc", "__pycache__", ".git", ".venv", ".egg", ".pytest")):
    """Recursively scan and count tokens in files matching pattern."""
    total = 0
    files = []
    for item in path.rglob(pattern):
        if any(ig in str(item) for ig in ignore):
            continue
        if item.is_file() and item.suffix in (".py", ".yaml", ".json", ".md", ".txt"):
            try:
                content = item.read_text()
                tokens = estimate_tokens(content)
                total += tokens
                files.append((item.name, tokens))
            except Exception:
                pass
    return total, sorted(files, key=lambda x: -x[1])


def main():
    world_tokens, world_files = scan_dir(ROOT / "world")
    repos_tokens, repos_files = scan_dir(ROOT / "repos")
    code_context = world_tokens + repos_tokens

    print("=" * 78)
    print("TOKEN COST COMPARISON: Pocket FDE (curated knowledge) vs Code Context")
    print("=" * 78)
    print(f"\nCode context (world/ + repos/): {code_context:,} tokens")
    print(f"  - world/ (ownership, observability, versions, flags, contracts): {world_tokens:,}")
    print(f"  - repos/ (8 team modules, flow harness): {repos_tokens:,}")
    print(f"\nIf the frontier model reads this context on every triage call:")
    for n_cases in [1, 10, 100]:
        cost_per_case_with_code = code_context + 8000  # ~8k for triage call itself (prompt + output)
        total = cost_per_case_with_code * n_cases
        print(f"  {n_cases:3d} cases × ({code_context:,} context + 8,000 triage) = {total:,} tokens")
    
    print(f"\nWith Pocket FDE (curated knowledge in vector store, not sent each time):")
    print(f"  Each triage call: ~8,000 tokens (retrieved chunks + redacted prompt + output)")
    print(f"  The repo overhead (5.5k tokens) is paid ONCE during indexing, not per call.")
    for n_cases in [1, 10, 100]:
        total = 8000 * n_cases + code_context  # code context once
        per_case = total / n_cases
        print(f"  {n_cases:3d} cases × 8,000 + {code_context:,} initial index = {total:,} total ({per_case:,.0f} per case)")
    
    print(f"\nSavings after breakeven point (~{code_context // 8000 + 1} cases):")
    print(f"  Pocket FDE: {8000:,} tokens/case")
    print(f"  Code context: {code_context + 8000:,} tokens/case")
    print(f"  Ratio: {(code_context + 8000) / 8000:.1f}x more expensive per case with code context")
    
    print(f"\n" + "=" * 78)
    print("Note: This is a floor estimate (4 chars = 1 token). Real tokenization may vary.")
    print("Real code context would also include: framework docs, API specs, design docs, ...")
    print("=" * 78)


if __name__ == "__main__":
    main()
