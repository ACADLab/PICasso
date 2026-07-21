"""
Multi-Agent Orchestrator for photonic circuit design.

Coordinates a Generator agent and a Critic agent:
  1. Generator produces a YAML netlist
  2. Critic reviews it and identifies problems
  3. Generator revises based on critic feedback
  4. Final YAML is passed to the formal validation pipeline

Exposes the same ASK_LLM interface as single agents so the rest
of test_with_llm.py requires no structural changes.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """
    Orchestrates a Generator + Critic agent pair.

    Drop-in replacement for a single agent — exposes ASK_LLM()
    so test_with_llm.py doesn't need to change.
    """

    def __init__(self, generator_agent, critic_agent, max_critic_rounds: int = 2):
        """
        Initialize orchestrator.

        Args:
            generator_agent: Primary LLM agent that generates YAML netlists
            critic_agent: CriticAgent instance that reviews generated YAML
            max_critic_rounds: Max number of generate->critique->revise cycles
        """
        self.generator = generator_agent
        self.critic = critic_agent
        self.max_critic_rounds = max_critic_rounds

        # Expose model name for logging (uses generator's model)
        self.model = getattr(generator_agent, 'model', 'multi-agent')

        logger.info(
            f"Initialized MultiAgentOrchestrator: "
            f"generator={self.model}, "
            f"critic_rounds={max_critic_rounds}"
        )

    def ASK_LLM(self, system_prompt: str, user_q: str) -> str:
        """
        Generate a YAML netlist using the generator+critic loop.

        Matches the single-agent ASK_LLM interface exactly.

        Args:
            system_prompt: System prompt / framework rules for the generator
            user_q: User query containing the problem description

        Returns:
            Final YAML string after critic review and revision
        """
        # Extract problem description from user_q for the critic
        problem_desc = self._extract_problem(user_q)

        # Initial generation
        logger.info("🤖 Generator: producing initial YAML...")
        yaml_output = self.generator.ASK_LLM(system_prompt, user_q)

        # Critic review + revision loop
        for round_num in range(1, self.max_critic_rounds + 1):
            logger.info(f"🔍 Critic: reviewing YAML (round {round_num}/{self.max_critic_rounds})...")
            review = self.critic.review(yaml_output, problem_desc)

            logger.info(f"🔍 Critic raw response: {review['raw_response'][:300]}")
            logger.info(f"🔍 Critic parsed — issues_found={review['issues_found']}, confidence={review.get('confidence','?')}, problems={review['problems']}")

            if not review["issues_found"]:
                logger.info(f"✅ Critic: no issues found on round {round_num}")
                break

            feedback = self.critic.format_feedback(review)
            logger.info(
                f"⚠️  Critic found {len(review['problems'])} issue(s) — "
                f"sending feedback to generator"
            )
            for problem in review["problems"]:
                logger.info(f"   - {problem}")

            # Build revised prompt with critic feedback
            revised_query = (
                f"{user_q}\n\n"
                f"{feedback}\n\n"
                f"Generate a corrected YAML that fixes all the problems above."
            )

            logger.info(f"🤖 Generator: revising YAML based on critic feedback...")
            yaml_output = self.generator.ASK_LLM(system_prompt, revised_query)

        return yaml_output

    def ask_llm(self, system_prompt: str, user_q: str) -> str:
        """Lowercase alias for ASK_LLM."""
        return self.ASK_LLM(system_prompt, user_q)

    def start_new_conversation(self):
        """Reset both agents."""
        if hasattr(self.generator, 'start_new_conversation'):
            self.generator.start_new_conversation()

    def _extract_problem(self, user_q: str) -> str:
        """
        Extract the problem description from the user query.
        Looks for content after 'Problem:' or returns the full query.
        """
        if "Problem:" in user_q:
            parts = user_q.split("Problem:", 1)
            if len(parts) > 1:
                # Take up to the next blank line or end
                problem_text = parts[1].strip()
                return problem_text.split("\n\n")[0].strip()
        return user_q[:500]  # Fallback: first 500 chars
