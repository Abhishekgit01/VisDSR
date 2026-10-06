"""Add a fresh XGrammar logits processor to the unchanged pinned provider."""
from __future__ import annotations

import importlib.metadata
import time
from functools import partial

from eval.providers.local import LocalModel
from interventions.protocol import grammar


class InterventionModel(LocalModel):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.compiler = None
        self.compiled = {}

    def answer(self, case: dict, task: dict, image: bytes | None, settings: dict) -> dict:
        if not case.get("grammar", False):
            return self.call_model(case["user_prompt"], image, settings)
        import xgrammar as xgr
        from xgrammar.contrib.hf import LogitsProcessor
        if importlib.metadata.version("xgrammar") != "0.2.8":
            raise RuntimeError("install the pinned XGrammar version before intervention inference")
        started = time.monotonic()
        if self.compiler is None:
            vocab = self.model.get_output_embeddings().weight.shape[0]
            info = xgr.TokenizerInfo.from_huggingface(self.processor.tokenizer, vocab_size=vocab)
            self.compiler = xgr.GrammarCompiler(info, max_threads=2)
        rule = grammar(task)
        if rule not in self.compiled:
            self.compiled[rule] = self.compiler.compile_grammar(xgr.Grammar.from_ebnf(rule))
        processor = LogitsProcessor(self.compiled[rule])
        setup_seconds = time.monotonic() - started
        original_generate = self.model.generate
        self.model.generate = partial(original_generate, logits_processor=[processor])
        try:
            response = self.call_model(case["user_prompt"], image, settings)
        finally:
            self.model.generate = original_generate
        return {**response, "grammar_engine": "xgrammar", "grammar_version": "0.2.8",
                "grammar_setup_seconds": setup_seconds}


def decoder_check() -> None:
    """Compile all task grammars with each actual tokenizer, without model weights."""
    import json
    import torch
    import xgrammar as xgr
    from transformers import AutoConfig, AutoTokenizer
    from xgrammar.contrib.hf import LogitsProcessor
    from diagnostics.protocol import load_panel
    frozen, tasks, _ = load_panel()
    for model in frozen["models"]:
        tokenizer = AutoTokenizer.from_pretrained(model["id"], revision=model["revision"])
        config = AutoConfig.from_pretrained(model["id"], revision=model["revision"])
        vocab = config.get_text_config().vocab_size
        info = xgr.TokenizerInfo.from_huggingface(tokenizer, vocab_size=vocab)
        compiler = xgr.GrammarCompiler(info, max_threads=2)
        for task in tasks:
            compiled = compiler.compile_grammar(xgr.Grammar.from_ebnf(grammar(task)))
            # Deliberately use arbitrary parents, not simulator answers. The
            # grammar must accept semantically wrong maps without filtering.
            answer = {"steps": []}
            for number, operation in enumerate(task["operations"], 1):
                step = {"op": number, "state": {name: "A" for name in task["initial"]}}
                if operation["kind"] == "find":
                    step["find_result"] = "A"
                answer["steps"].append(step)
            raw = json.dumps(answer, separators=(",", ":"))
            matcher = xgr.GrammarMatcher(compiled)
            tokens = tokenizer.encode(raw, add_special_tokens=False)
            if not all(matcher.accept_token(token) for token in tokens):
                raise RuntimeError("task grammar rejects a structurally correct, arbitrary answer")
            if not matcher.accept_token(info.stop_token_ids[0]) or not matcher.is_terminated():
                raise RuntimeError("task grammar does not terminate correctly")
            for index in range(torch.cuda.device_count()):
                device = f"cuda:{index}"
                processor = LogitsProcessor(compiled)
                ids = torch.tensor([[info.stop_token_ids[0]]], device=device)
                for token in tokens[:2]:
                    scores = torch.full((1, vocab), float("-inf"), device=device)
                    scores[0, token] = 0
                    masked = processor(ids, scores)
                    if not torch.isfinite(masked[0, token]).item():
                        raise RuntimeError("GPU grammar mask rejected a valid token")
                    ids = torch.cat((ids, torch.tensor([[token]], device=device)), dim=1)
                torch.cuda.synchronize(index)
        print(f"DECODER CHECK PASSED: {model['name']}, 8 grammars, actual tokenizer, no weights loaded", flush=True)
    print(f"GPU MASK CHECK: {torch.cuda.device_count()} CUDA devices tested (zero means CPU checks only)", flush=True)
