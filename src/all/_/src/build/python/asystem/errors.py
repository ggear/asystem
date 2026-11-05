class GateError(ValueError):
    def __init__(self, stage, gate, cause):
        super().__init__(f"gate not met stage [{stage}] gate [{gate}] [{cause}]")
        self.stage = stage
        self.gate = gate
        self.cause = cause
