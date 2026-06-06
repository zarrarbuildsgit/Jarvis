"""
JARVIS Vision Model Router
Phase 5: GTX 1050 Ti-aware lazy loading and model routing.
"""

from __future__ import annotations

import gc
import time
from typing import Dict, List, Optional

import torch
from PIL import Image
from loguru import logger

from backend.optimization import GTX1050TiProfile, detect_profile


class VisionRouter:
    def __init__(self, lazy_load: bool = True, optimization_profile: str | None = None):
        self.models: Dict[str, dict] = {}
        self.default_model: Optional[str] = None
        self.device = self._get_device()
        if optimization_profile == "gtx1050ti":
            self.profile = GTX1050TiProfile()
            self.profile.apply_environment()
        else:
            self.profile = detect_profile()
        self.lazy_load = lazy_load
        self.model_specs = {
            "smolvlm": {
                "id": "HuggingFaceTB/SmolVLM-Instruct",
                "class": "AutoModelForVision2Seq",
                "role": "fast_check",
            },
            "florence2": {
                "id": "microsoft/Florence-2-base-ft",
                "class": "AutoModelForVision2Seq",
                "role": "ui_detection",
            },
            "qwen": {
                "id": "Qwen/Qwen2.5-VL-3B-Instruct",
                "class": "Qwen2VLForConditionalGeneration",
                "role": "complex_reasoning",
            },
        }
        logger.info("Vision device=%s profile=%s lazy=%s", self.device, "gtx1050ti" if self.profile else "default", lazy_load)
        if not lazy_load:
            self._initialize_models()

    def _initialize_models(self) -> None:
        order = ["smolvlm", "florence2", "qwen"]
        if self.profile:
            order = list(self.profile.prefer_models)  # avoid qwen on 4GB by default
        for name in order:
            self._load_model(name)
        self._set_default()

    def _load_model(self, name: str) -> bool:
        if name in self.models:
            return True
        if name == "qwen" and self.profile:
            logger.warning("Skipping Qwen by default on GTX1050Ti/4GB profile. Use a smaller model or disable profile to force it.")
            return False
        spec = self.model_specs.get(name)
        if not spec:
            return False
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq
            processor = AutoProcessor.from_pretrained(spec["id"], trust_remote_code=True)
            dtype = torch.float16 if self.device == "cuda" else torch.float32
            kwargs = {"torch_dtype": dtype, "trust_remote_code": True}
            if self.profile:
                kwargs.update(self.profile.model_kwargs(self.device))
            if name == "qwen":
                from transformers import Qwen2VLForConditionalGeneration
                model = Qwen2VLForConditionalGeneration.from_pretrained(spec["id"], **kwargs)
            else:
                # 8-bit loading already chooses device_map; otherwise move manually.
                model = AutoModelForVision2Seq.from_pretrained(spec["id"], **kwargs)
                if not kwargs.get("device_map"):
                    model = model.to(self.device)
            self.models[name] = {"processor": processor, "model": model}
            self._set_default()
            logger.info("✓ %s loaded", name)
            return True
        except Exception as exc:
            logger.warning("%s failed: %s", name, exc)
            self._clear_cuda()
            return False

    def unload_model(self, name: str) -> None:
        if name in self.models:
            del self.models[name]
            self._clear_cuda()
            self._set_default()

    def _clear_cuda(self) -> None:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    def _set_default(self) -> None:
        for name in ["smolvlm", "florence2", "qwen"] if self.profile else ["qwen", "florence2", "smolvlm"]:
            if name in self.models:
                self.default_model = name
                return
        self.default_model = None

    def _get_device(self) -> str:
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            return "cuda" if vram >= 3.5 else "cpu"
        return "cpu"

    def route_query(self, query: str, screenshot: Optional[Image.Image] = None) -> Dict:
        complexity = self._assess_complexity(query)
        model_map = {"simple": "smolvlm", "ui_detection": "florence2", "complex": "qwen"}
        if self.profile and complexity == "complex":
            model_map["complex"] = "florence2"
        fallback_order = ["smolvlm", "florence2", "qwen"] if self.profile else ["qwen", "florence2", "smolvlm"]
        model_name = model_map.get(complexity, self.default_model or "smolvlm")
        if model_name not in self.models:
            self._load_model(model_name)
        if model_name not in self.models:
            for fb in fallback_order:
                if fb in self.models or self._load_model(fb):
                    model_name = fb
                    break
            else:
                return {"error": "No vision models available", "complexity": complexity}
        start_time = time.time()
        result = self._run_model(model_name, query, screenshot)
        inference_time = time.time() - start_time
        return {
            "model": model_name,
            "result": result,
            "inference_time_ms": round(inference_time * 1000, 2),
            "complexity": complexity,
            "profile": "gtx1050ti" if self.profile else "default",
        }

    def _assess_complexity(self, query: str) -> str:
        ql = query.lower()
        simple_kw = ["what is", "describe", "read", "text", "simple"]
        ui_kw = ["click", "button", "menu", "icon", "window", "find", "locate"]
        if any(kw in ql for kw in simple_kw):
            return "simple"
        if any(kw in ql for kw in ui_kw):
            return "ui_detection"
        return "complex"

    def _run_model(self, model_name: str, query: str, screenshot: Optional[Image.Image]) -> str:
        model_data = self.models.get(model_name)
        if not model_data:
            return f"Error: Model {model_name} not available"
        try:
            if model_name == "smolvlm":
                return self._run_smolvlm(model_data, query, screenshot)
            if model_name == "florence2":
                return self._run_florence2(model_data, query, screenshot)
            if model_name == "qwen":
                return self._run_qwen(model_data, query, screenshot)
        except Exception as exc:
            logger.error("Model %s inference failed: %s", model_name, exc)
            return f"Error: {exc}"
        return "No model runner available"

    def _run_smolvlm(self, model_data: Dict, query: str, screenshot: Optional[Image.Image]) -> str:
        if screenshot is None:
            return "No screenshot provided"
        processor, model = model_data["processor"], model_data["model"]
        inputs = processor(text=query, images=screenshot, return_tensors="pt")
        try:
            device = next(model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
        except Exception:
            pass
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=128 if self.profile else 256)
        return processor.decode(generated[0], skip_special_tokens=True)

    def _run_florence2(self, model_data: Dict, query: str, screenshot: Optional[Image.Image]) -> str:
        if screenshot is None:
            return "No screenshot provided"
        processor, model = model_data["processor"], model_data["model"]
        task_prompt = "<OCR>" if any(k in query.lower() for k in ["button", "click", "read", "text"]) else "<CAPTION>"
        inputs = processor(text=task_prompt, images=screenshot, return_tensors="pt")
        try:
            device = next(model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
        except Exception:
            pass
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=128 if self.profile else 256, do_sample=False)
        return processor.decode(generated[0], skip_special_tokens=True)

    def _run_qwen(self, model_data: Dict, query: str, screenshot: Optional[Image.Image]) -> str:
        if screenshot is None:
            return "No screenshot provided"
        processor, model = model_data["processor"], model_data["model"]
        messages = [{"role": "user", "content": [{"type": "image", "image": screenshot}, {"type": "text", "text": query}]}]
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = processor(text=[text], images=[screenshot], padding=True, return_tensors="pt")
        try:
            inputs = inputs.to(next(model.parameters()).device)
        except Exception:
            pass
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=256 if self.profile else 512, do_sample=False)
        generated_ids = generated[:, inputs["input_ids"].shape[1]:]
        return processor.decode(generated_ids[0], skip_special_tokens=True)

    def get_available_models(self) -> List[str]:
        return list(self.models.keys()) or ["lazy:not-loaded"]

    def get_model_info(self) -> Dict:
        info = {
            "device": self.device,
            "profile": self.profile.as_dict() if self.profile else None,
            "loaded": list(self.models.keys()),
            "lazy_load": self.lazy_load,
        }
        for name, data in self.models.items():
            try:
                model = data["model"]
                info[name] = {"device": str(next(model.parameters()).device), "parameters": sum(p.numel() for p in model.parameters())}
            except Exception:
                info[name] = {"device": "device_map/unknown"}
        return info
