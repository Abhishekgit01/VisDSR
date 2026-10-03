"""Local multimodal inference for the Kaggle smoke and later runs."""
from __future__ import annotations

import io
import os
import time

from PIL import Image

from eval.prompts import SYSTEM


def model_messages(prompt: str, optional_image: bytes | None) -> list[dict]:
    """Format both chat roles as multimodal processor content parts."""
    content = []
    if optional_image is not None:
        with Image.open(io.BytesIO(optional_image)) as source:
            content.append({"type": "image", "image": source.convert("RGB")})
    content.append({"type": "text", "text": prompt})
    return [{"role": "system", "content": [{"type": "text", "text": SYSTEM}]},
            {"role": "user", "content": content}]


class LocalModel:
    def __init__(self, settings: dict):
        # Kaggle also ships TensorFlow; this experiment uses only PyTorch.
        os.environ["USE_TF"] = "0"
        os.environ["USE_TORCH"] = "1"
        import torch
        from huggingface_hub import model_info
        import transformers
        from transformers import AutoProcessor, BitsAndBytesConfig

        if transformers.__version__ != settings["transformers_version"]:
            raise RuntimeError("install the pinned Transformers version before inference")

        if not torch.cuda.is_available():
            raise RuntimeError("a CUDA GPU is required for local model inference")
        if settings["do_sample"] is not False or settings["num_beams"] != 1:
            raise ValueError("VisDSR requires greedy decoding")
        if settings["provider"] not in ("qwen3_vl", "internvl35_hf"):
            raise ValueError(f"unsupported local provider: {settings['provider']}")
        self.torch = torch
        self.transformers = transformers
        self.settings = dict(settings)
        self.model_id = settings["id"]
        self.revision = model_info(self.model_id, revision=settings["revision"]).sha
        if self.revision != settings["revision"]:
            raise RuntimeError("model revision did not resolve to the pinned commit")
        dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        self.compute_dtype = str(dtype)
        quantization = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=dtype,
        )
        model_options = {"revision": self.revision, "quantization_config": quantization,
                         "dtype": dtype, "device_map": "auto"}
        if settings["provider"] == "qwen3_vl":
            from transformers import Qwen3VLForConditionalGeneration
            model_class = Qwen3VLForConditionalGeneration
            self.processor = AutoProcessor.from_pretrained(self.model_id, revision=self.revision)
            model_options["attn_implementation"] = "sdpa"
            self.attention = "sdpa"
        else:
            from transformers import AutoModelForImageTextToText
            model_class = AutoModelForImageTextToText
            self.processor = AutoProcessor.from_pretrained(
                self.model_id, revision=self.revision, trust_remote_code=True)
            model_options["trust_remote_code"] = True
            self.attention = "framework default"
        self.model = model_class.from_pretrained(self.model_id, **model_options).eval()

    def call_model(self, prompt: str, optional_image: bytes | None, settings: dict) -> dict:
        if settings["id"] != self.model_id:
            raise ValueError("model ID changed after loading")
        messages = model_messages(prompt, optional_image)
        started = time.monotonic()
        inputs = self.processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt",
        ).to(self.model.device)
        inputs.pop("token_type_ids", None)
        for index in range(self.torch.cuda.device_count()):
            self.torch.cuda.reset_peak_memory_stats(index)
        with self.torch.inference_mode():
            generated = self.model.generate(
                **inputs,
                do_sample=False,
                num_beams=1,
                max_new_tokens=settings["max_output_tokens"],
            )
        for index in range(self.torch.cuda.device_count()):
            self.torch.cuda.synchronize(index)
        output_ids = generated[0][inputs["input_ids"].shape[-1]:]
        latency = time.monotonic() - started
        gpu_peaks = [self.torch.cuda.max_memory_allocated(index)
                     for index in range(self.torch.cuda.device_count())]
        return {
            "raw_text": self.processor.decode(output_ids, skip_special_tokens=True,
                                              clean_up_tokenization_spaces=False),
            "latency": latency,
            "latency_s": latency,
            "model_id": self.model_id,
            "revision": self.revision,
            "settings": {**self.settings, "compute_dtype": self.compute_dtype,
                         "attention": self.attention, "transformers_version": self.transformers.__version__,
                         "torch_version": self.torch.__version__,
                         "generation_config": self.model.generation_config.to_dict()},
            "gpu_peak_bytes": max(gpu_peaks),
            "gpu_peaks_bytes": gpu_peaks,
            "gpus": [{"name": self.torch.cuda.get_device_name(index),
                      "vram_bytes": self.torch.cuda.get_device_properties(index).total_memory}
                     for index in range(self.torch.cuda.device_count())],
        }
