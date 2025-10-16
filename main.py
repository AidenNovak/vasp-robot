#!/usr/bin/env python3
"""
VASP-HPC Orchestrator - Main Entry Point
A Claude Code agent for managing VASP calculations on HPC clusters.
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from src.vasp_robot import create_vasp_agent


async def main():
    """Main entry point for the VASP orchestrator agent"""

    # Load environment variables
    load_dotenv()

    # Check for required API key
    api_key = os.getenv("KIMI_API_KEY")
    if not api_key:
        print("Error: KIMI_API_KEY environment variable not set")
        print("Please set your API key in a .env file or environment variable")
        print("See .env.example for the required format")
        return

    # Create and initialize the agent
    print("🚀 Initializing VASP-HPC Orchestrator Agent...")

    try:
        agent_handler = create_vasp_agent()
        print("✅ Agent initialized successfully!")
        print()
        print("📋 Available capabilities:")
        print("  • Plan VASP calculations from natural language")
        print("  • Generate input files (INCAR, KPOINTS, POSCAR, POTCAR)")
        print("  • Create Slurm submission scripts")
        print("  • Human-in-the-loop approval before submission")
        print("  • Submit and monitor HPC jobs")
        print("  • Fetch and analyze results")
        print()
        print("💡 Example usage:")
        print('  "Design 3 geometry optimizations for Ca2N sweeping ENCUT 450/500/550"')
        print()
        print("🔧 Ready to process VASP calculation requests...")

        # Start interactive session
        print("\nEnter your VASP calculation requests (or 'quit' to exit):")

        while True:
            try:
                user_input = input("\nVASP> ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break

                if not user_input:
                    continue

                print(f"\n🔄 Processing: {user_input}")
                response = await agent_handler(user_input)
                print(f"\n🤖 Agent Response:\n{response}")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")

    except Exception as e:
        print(f"❌ Failed to initialize agent: {e}")
        print("Please check your configuration and API key")


if __name__ == "__main__":
    asyncio.run(main())
