from mlserver.types import InferenceRequest, InferenceResponse, ResponseOutput, TensorData

from mlserver import MLModel
from project_runtime.project import load_project


class ProjectRuntime(MLModel):
    async def load(self):
        parameters = self.settings.parameters
        assert parameters is not None and parameters.uri is not None
        self._project = load_project(parameters.uri)
        self.ready = True
        return self.ready

    async def predict(self, payload: InferenceRequest) -> InferenceResponse:
        inputs = {entry.name: list(getattr(entry.data, "root", entry.data)) for entry in payload.inputs}
        result = self._project.predict(inputs)
        datatypes = {entry["name"]: entry["datatype"] for entry in self._project.signature["outputs"]}
        outputs = [ResponseOutput(name=name, shape=[len(values)], datatype=datatypes[name], data=TensorData(root=values)) for name, values in result.items()]
        return InferenceResponse(model_name=self.name, model_version=self.version, outputs=outputs)
