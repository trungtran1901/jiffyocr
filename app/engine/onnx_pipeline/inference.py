import numpy as np
import onnxruntime as ort

from app.engine.onnx_pipeline.config import ORT_PROVIDERS


class OnnxModel:
    def __init__(self, model_path):
        self.session = ort.InferenceSession(str(model_path), providers=ORT_PROVIDERS)
        self.input_name = self.session.get_inputs()[0].name
        self.output_names = [o.name for o in self.session.get_outputs()]

    def run(self, input_tensor: np.ndarray):
        outputs = self.session.run(self.output_names, {self.input_name: input_tensor})
        return dict(zip(self.output_names, outputs))
