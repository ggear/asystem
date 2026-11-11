from mlserver.types import InferenceRequest, InferenceResponse, ResponseOutput, TensorData

from mlserver import MLModel
from serving.model.loader import load


class ProjectRuntime(MLModel):
    async def load(self):
        parameters = self.settings.parameters
        assert parameters is not None and parameters.uri is not None
        self._model = load(parameters.uri)
        self.ready = True
        return self.ready

    async def predict(self, payload: InferenceRequest) -> InferenceResponse:
        inputs = {entry.name: list(entry.data.root) for entry in payload.inputs}
        result = self._model.predict(inputs)
        datatypes = {entry["name"]: entry["datatype"] for entry in self._model.signature()["outputs"]}
        outputs = [ResponseOutput(name=name, shape=[len(values)], datatype=datatypes[name], data=TensorData(root=values)) for name, values in result.items()]
        return InferenceResponse(model_name=self.name, model_version=self.version, outputs=outputs)
