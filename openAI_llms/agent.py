from pathlib import Path
from typing import List, Optional
from openai import OpenAI

FILE_ID = "file-4zemm4ei5rhvSuWtDxe2Xg"

# try:
#     import pypdf
# except ImportError:
#     pypdf = None
#     print("[LLMAgent] NOTE: install `pypdf` to embed PDF text automatically.")


class LLMAgent:
    def __init__(
        self,
        api_key: str = API_KEY",
        model: str = "gpt-4o",
		file_id = FILE_ID,
        char_limit: int = 50_000,
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model

        # self.pdf_text = ""
        # if pdf_path and Path(pdf_path).is_file() and pypdf:
        #     try:
        #         reader = pypdf.PdfReader(pdf_path)
        #         text = "\n".join(pg.extract_text() or "" for pg in reader.pages)
        #         self.pdf_text = text[:char_limit]
        #         print(f"[LLMAgent] embedded {len(self.pdf_text):,} chars of '{pdf_path}'")
        #     except Exception as e:
        #         print(f"[LLMAgent] WARNING: could not read '{pdf_path}': {e}")
        # elif pdf_path and not pypdf:
        #     print("[LLMAgent] install pypdf to enable PDF parsing.")
        # else:
        #     print("[LLMAgent] PDF not found – continuing without extra context.")

        self.hist: List[dict] = []

    def _prepped_system(self, base_prompt: str) -> dict:
        # if self.pdf_text:
        #     merged = f"{base_prompt}\n\n---\nReference (GDSFactory component list):\n{self.pdf_text}\n---"
        # else:
        merged = base_prompt
        return {"role": "system", "content": merged}

    def _call(self, messages: List[dict]) -> str:
        resp = self.client.chat.completions.create(model=self.model, messages=messages,
                                                   attachments=[{"file_id": FILE_ID, "tools": [{"type": "file_search"}]}])
        return resp.choices[0].message.content


    def ASK_LLM(self, system_prompt: str, user_q: str) -> str:
        msgs = [
            self._prepped_system(system_prompt),
            {"role": "user", "content": user_q},
        ]
        return self._call(msgs)

    def ASK_LLM_iterate(self, system_prompt: str, user_q: str, clear_context=False) -> str:
        if clear_context or not self.hist:
            self.hist = [
                self._prepped_system(system_prompt),
            ]

        self.hist.append({"role": "user", "content": user_q})
        answer = self._call(self.hist)
        self.hist.append({"role": "assistant", "content": answer})
        return answer

    def start_new_conversation(self):
        self.hist = []

