from __future__ import annotations

from src.state import create_initial_state
from src.workflow.main import run_full_pipeline


def run_local_demo() -> None:
    """Run a local pipeline demo and print final feedback."""
    state = create_initial_state()
    final_state = run_full_pipeline(state)

    print("=== Final Feedback ===")
    print(final_state["final_feedback"])
    print("\n=== Logs ===")
    for line in final_state["logs"]:
        print(f"- {line}")


if __name__ == "__main__":
    run_local_demo()
