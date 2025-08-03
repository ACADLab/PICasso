from typing import List
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM


class HFAgent:
    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-Instruct-v0.2",
        *,
        device: str | None = None,
        max_new_tokens: int = 2048,
        temperature: float = 0.3,
        top_p: float = 0.95,
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto" if self.device == "cuda" else None,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            trust_remote_code=True,
        )

        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.hist: List[dict] = []

        self._has_template = hasattr(self.tokenizer, "apply_chat_template")

    # ------------------------------------------------------------------ #
    # Internal helpers                                                    #
    # ------------------------------------------------------------------ #
    def _chat_to_prompt(self, messages: List[dict]) -> str:
        if self._has_template:
            return self.tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

        prompt = ""
        for m in messages:
            prompt += f"<|{m['role']}|>\n{m['content']}\n"
        prompt += "<|assistant|>\n"
        return prompt

    def _call(self, messages: List[dict]) -> str:
        prompt = self._chat_to_prompt(messages)

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        generated = outputs[0][inputs["input_ids"].shape[-1] :]
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip()

    # ------------------------------------------------------------------ #
    # Public API (matches original class)                            #
    # ------------------------------------------------------------------ #
    def ASK_LLM(self, system_prompt: str, user_q: str) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_q},
        ]
        return self._call(messages)

    def ASK_LLM_iterate(self, system_prompt: str, user_q: str, *, clear_context=False) -> str:
        if clear_context or not self.hist:
            self.hist = [{"role": "system", "content": system_prompt}]

        self.hist.append({"role": "user", "content": user_q})
        answer = self._call(self.hist)
        self.hist.append({"role": "assistant", "content": answer})
        return answer

    def start_new_conversation(self):
        self.hist = []

