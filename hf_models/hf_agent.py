from typing import List, Optional
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import logging

logger = logging.getLogger(__name__)


class HFAgent:
    """
    Local GPU agent for photonic circuit code generation.

    Features:
    - Multi-GPU support via device_map="auto"
    - Model caching for faster loading
    - Memory-efficient FP16 inference on GPU
    - Automatic fallback to CPU if GPU unavailable
    """

    def __init__(
        self,
        model_name: str = "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
        *,
        device: str | None = None,
        max_new_tokens: int = 2048,
        temperature: float = 0.3,
        top_p: float = 0.95,
        cache_dir: Optional[str] = None,
    ):
        # GPU detection and logging
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        if self.device == "cuda":
            gpu_count = torch.cuda.device_count()
            logger.info(f"🚀 Using {gpu_count} GPU(s) for model inference")
            for i in range(gpu_count):
                gpu_name = torch.cuda.get_device_name(i)
                gpu_mem = torch.cuda.get_device_properties(i).total_memory / 1e9
                logger.info(f"  GPU {i}: {gpu_name} ({gpu_mem:.1f} GB)")
        else:
            logger.warning("⚠️  No GPU detected - using CPU (will be slower)")

        # Load tokenizer with caching
        logger.info(f"Loading tokenizer: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
            cache_dir=cache_dir
        )

        # Load model with multi-GPU support and caching
        logger.info(f"Loading model: {model_name}")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map="auto" if self.device == "cuda" else None,  # Multi-GPU automatic
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            trust_remote_code=True,
            cache_dir=cache_dir,
            low_cpu_mem_usage=True,  # Reduce CPU memory during loading
        )

        logger.info(f"✅ Model loaded successfully on {self.device}")

        # Log memory usage if on GPU
        if self.device == "cuda":
            for i in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(i) / 1e9
                reserved = torch.cuda.memory_reserved(i) / 1e9
                logger.info(f"  GPU {i} Memory: {allocated:.2f} GB allocated, {reserved:.2f} GB reserved")

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

