"""Interactive CLI for AutoPlan AI.

Allows entering queries directly in the terminal, rendering the classification routing,
timeline execution steps, safety validator audits, and the final recommendation.
"""

import os
import sys
from pathlib import Path

# Configure paths so Python can locate the packages
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent / "framework"))
sys.path.append(str(Path(__file__).resolve().parent / "app"))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app.app import AutoPlanApp


def main():
    print("=" * 60)
    print("                  AUTOPLAN AI CLI TERMINAL                      ")
    print("=" * 60)
    print("Initializing AutoPlan AI Application. Please wait...")
    
    try:
        app = AutoPlanApp()
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize AutoPlan AI: {e}")
        return

    print("Initialization complete! Type 'exit' or 'quit' to close.\n")

    while True:
        try:
            query = input("Ask a question: ").strip()
            if not query:
                continue
            if query.lower() in ("exit", "quit"):
                print("Goodbye!")
                break

            print("\n" + "-" * 50)
            print("⏳ Processing query...")
            print("-" * 50)

            result = app.run_query(query)

            # Print Router Decision
            route = result.get("route_decision", "unknown").upper()
            print(f"\n🧭 [ROUTE DECISION]: {route}")

            # Print execution trace timeline
            trace = result.get("execution_trace", [])
            if trace:
                print("\n🎬 [EXECUTION TIMELINE]:")
                for step in trace:
                    node = step.get("node", "unknown").upper()
                    action = step.get("action", "")
                    reasoning = step.get("metadata", {}).get("reasoning", "")
                    print(f"  * {node} | {action}")
                    if reasoning:
                        print(f"    Reasoning: {reasoning}")

            # Print strategy recommendation / response
            recommendation = result.get("recommendation", "")
            print("\n📄 [RESPONSE]:")
            print(recommendation)
            
            print("\n" + "=" * 60 + "\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\n[ERROR] An error occurred: {e}\n")


if __name__ == "__main__":
    main()
