"""
JARVIS Vision Model Router
SmolVLM (fast checks) → Florence-2 (UI detection) → Qwen2.5-VL-3B (complex reasoning)
"""

import torch
from PIL import Image
from typing import Optional, Dict, List
from loguru import logger
import time

class VisionRouter:
    def __init__(self):
        self.models = {}
        self.default_model = None
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize vision models based on available hardware"""
        device = self._get_device()
        logger.info(f"Using device: {device}")
        
        # SmolVLM (lightest)
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq
            self.models["smolvlm"] = {
                "processor": AutoProcessor.from_pretrained("HuggingFaceTB/SmolVLM-Instruct"),
                "model": AutoModelForVision2Seq.from_pretrained(
                    "HuggingFaceTB/SmolVLM-Instruct",
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32
                ).to(device)
            }
            logger.info("✓ SmolVLM loaded")
        except Exception as e:
            logger.warning(f"SmolVLM failed: {e}")
        
        # Florence-2 (UI specialist)
        try:
            from transformers import AutoProcessor, AutoModelForVision2Seq
            self.models["florence2"] = {
                "processor": AutoProcessor.from_pretrained("microsoft/Florence-2-base-ft"),
                "model": AutoModelForVision2Seq.from_pretrained(
                    "microsoft/Florence-2-base-ft",
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32
                ).to(device)
            }
            logger.info("✓ Florence-2 loaded")
        except Exception as e:
            logger.warning(f"Florence-2 failed: {e}")
        
        # Qwen2.5-VL-3B (complex reasoning)
        try:
            from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
            self.models["qwen"] = {
                "processor": AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct"),
                "model": Qwen2VLForConditionalGeneration.from_pretrained(
                    "Qwen/Qwen2.5-VL-3B-Instruct",
                    torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                    device_map="auto" if device == "cuda" else None
                )
            }
            logger.info("✓ Qwen2.5-VL-3B loaded")
        except Exception as e:
            logger.warning(f"Qwen2.5-VL-3B failed: {e}")
        
        # Set default
        for name in ["qwen", "florence2", "smolvlm"]:
            if name in self.models:
                self.default_model = name
                break
    
    def _get_device(self):
        """Determine best available device"""
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory / (102**3)
            return "cuda" if vram >= 4 else "cpu"
        return "cpu"
    
    def route_query(self, query: str, screenshot: Optional[Image.Image] = None) -> Dict:
        """Route query to best model based on complexity"""
        complexity = self._assess_complexity(query)
        
        model_map = {"simple": "smolvlm", "ui_detection": "florence2", "complex": "qwen"}
        fallback_order = ["qwen", "florence2", "smolvlm"]
        
        model_name = model_map.get(complexity, self.default_model)
        
        # Fallback if preferred model not loaded
        if model_name not in self.models:
            for fb in fallback_order:
                if fb in self.models:
                    model_name = fb
                    break
            else:
                return {"error": "No vision models available"}
        
        start_time = time.time()
        result = self._run_model(model_name, query, screenshot)
        inference_time = time.time() - start_time
        
        return {
            "model": model_name,
            "result": result,
            "inference_time_ms": round(inference_time * 1000, 2),
            "complexity": complexity
        }
    
    def _assess_complexity(self, query: str) -> str:
        """Assess query complexity"""
        ql = query.lower()
        simple_kw = ["what is", "describe", "read", "text", "simple"]
        ui_kw = ["click", "button", "menu", "icon", "window", "find", "locate"]
        
        if any(kw in ql for kw in simple_kw):
            return "simple"
        if any(kw in ql for kw in ui_kw):
            return "ui_detection"
        return "complex"
    
    def _run_model(self, model_name: str, query: str, screenshot: Optional[Image.Image]) -> str:
        """Run inference with specified model"""
        model_data = self.models.get(model_name)
        if not model_data:
            return f"Error: Model {model_name} not available"
        
        try:
            if model_name == "smolvlm":
                return self._run_smolvlm(model_data, query, screenshot)
            elif model_name == "florence2":
                return self._run_florence2(model_data, query, screenshot)
            elif model_name == "qwen":
                return self._run_qwen(model_data, query, screenshot)
        except Exception as e:
            logger.error(f"Model {model_name} inference failed: {e}")
            return f"Error: {str(e)}"
    
    def _run_smolvlm(self, model_data: Dict, query: str, screenshot: Optional[Image.Image]) -> str:
        """Run SmolVLM inference"""
        processor = model_data["processor"]
        model = model_data["model"]
        
        if screenshot is None:
            return "No screenshot provided"
        
        inputs = processor(text=query, images=screenshot, return_tensors="pt")
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=256)
        
        return processor.decode(generated[0], skip_special_tokens=True)
    
    def _run_florence2(self, model_data: Dict, query: str, screenshot: Optional[Image.Image]) -> str:
        """Run Florence-2 inference (UI detection specialist)"""
        processor = model_data["processor"]
        model = model_data["model"]
        
        if screenshot is None:
            return "No screenshot provided"
        
        task_prompt = "<OPEN_VOCABULARY_DETECTION>"
        if "button" in query.lower() or "click" in query.lower():
            task_prompt = "<OCR>"
        elif "find" in query.lower() or "locate" in query.lower():
            task_prompt = "<CAPTION>"
        
        inputs = processor(text=task_prompt, images=screenshot, return_tensors="pt")
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=256, do_sample=False)
        
        return processor.decode(generated[0], skip_special_tokens=True)
    
    def _run_qwen(self, model_data: Dict, query: str, screenshot: Optional[Image.Image]) -> str:
        """Run Qwen2.5-VL-3B inference (complex reasoning)"""
        processor = model_data["processor"]
        model = model_data["model"]
        
        if screenshot is None:
            return "No screenshot provided"
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": screenshot},
                    {"type": "text", "text": query}
                ]
            }
        ]
        
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs = [screenshot]
        inputs = processor(text=[text], images=image_inputs, padding=True, return_tensors="pt")
        inputs = inputs.to(model.device)
        
        with torch.no_grad():
            generated = model.generate(**inputs, max_new_tokens=512, do_sample=False)
        
        generated_ids = generated[:, inputs["input_ids"].shape[1]:]
        return processor.decode(generated_ids[0], skip_special_tokens=True)
    
    def get_available_models(self) -> List[str]:
        return list(self.models.keys())
    
    def get_model_info(self) -> Dict:
        return {
            name: {
                "device": str(data["model"].device),
                "parameters": sum(p.numel() for p in data["model"].parameters())
            }
            for name, data in self.models.items()
        }
