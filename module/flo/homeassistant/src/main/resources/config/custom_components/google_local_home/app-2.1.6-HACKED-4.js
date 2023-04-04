"use strict";
/// <reference types="@google/local-home-sdk" />
var App = smarthome.App;
var Constants = smarthome.Constants;
var DataFlow = smarthome.DataFlow;
var Execute = smarthome.Execute;
var Intents = smarthome.Intents;
var IntentFlow = smarthome.IntentFlow;
var ErrorCode = IntentFlow.ErrorCode;
const VERSION = "2.1.6-HACKED-4";
class RequestResponseHandler {
    constructor(intent, request, options = {}) {
        this.intent = intent;
        this.request = request;
        this.options = options;
        this.logMessage(`GA request incoming ...`, this.request);
    }
    async getDeviceManager() {
        if (this._deviceManager) {
            return this._deviceManager;
        }
        this._deviceManager = await app.getDeviceManager();
        this.haVersion = (this.options.extractHAVersion || getHAVersionFromProxyDevice)(this._deviceManager);
        return this._deviceManager;
    }
    createResponse(payload) {
        return {
            requestId: this.request.requestId,
            payload,
        };
    }
    /** Create and log the error. */
    createError(errorCode, msg, ...extraLog) {
        this.logError(`Error ${errorCode}`, msg, ...extraLog);
        if (this.haVersion) {
            msg += ` (HA/${this.haVersion})`;
        }
        return new IntentFlow.HandlerError(this.request.requestId, errorCode, msg);
    }
    /** Get Home Assistant info stored in device custom data. */
    getHassCustomData(deviceManager) {
        for (const device of deviceManager.getRegisteredDevices()) {
            const customData = device.customData;
            if (customData && "webhookId" in customData && "httpPort" in customData) {
                return customData;
            }
        }
        throw this.createError(ErrorCode.DEVICE_VERIFICATION_FAILED, `Unable to find HASS connection info.`, deviceManager.getRegisteredDevices());
    }
    get logPrefix() {
        return `[Intent:${this.intent} ${this.haVersion ? `HAAS Version:${this.haVersion}` : ''}]`;
    }
    logMessage(msg, ...extraLog) {
        if (extraLog.length > 0) {
            msg += "\n";
        }
        console.log(this.logPrefix, msg, ...extraLog);
    }
    logError(msg, ...extraLog) {
        if (extraLog.length > 0) {
            msg += "\n";
        }
        console.error(this.logPrefix, msg, ...extraLog);
    }
    async forwardRequest(targetDeviceId, isRetry = false) {
        const deviceManager = await this.getDeviceManager();
        const haVersion = this.haVersion;
        this.logMessage(`GA request forwarding ...`, this.request);
        if (this.options.supportedHAVersion &&
            (!haVersion ||
                !atleastVersion(haVersion, ...this.options.supportedHAVersion))) {
            this.logMessage("Intent not supported by HA version. Returning empty response");
            return this.createResponse({});
        }
        const deviceData = this.getHassCustomData(deviceManager);
        const command = new DataFlow.HttpRequestData();
        command.method = Constants.HttpOperation.POST;
        command.requestId = this.request.requestId;
        command.deviceId = targetDeviceId;
        command.port = deviceData.httpPort;
        command.path = `/api/webhook/${deviceData.webhookId}`;
        command.data = JSON.stringify(this.request);
        command.dataType = "application/json";
        command.additionalHeaders = {
            "HA-Cloud-Version": VERSION,
        };
        this.logMessage("HAAS request posting ...", command);
        let rawResponse;
        try {
            rawResponse = (await deviceManager.send(command));
        }
        catch (err) {
            this.logError("Error making request", err);
            // Errors coming out of `deviceManager.send` are already Google errors.
            throw err;
        }
        // Detect the response if the webhook is not registered.
        // This can happen if user logs out from cloud while Google still
        // has devices synced or if Home Assistant is restarting and Google Assistant
        // integration is not yet initialized.
        if (rawResponse.httpResponse.statusCode === 200 &&
            !rawResponse.httpResponse.body) {
            // Retry in case it's because of initialization.
            if (!isRetry &&
                [
                    Intents.IDENTIFY,
                    Intents.PROXY_SELECTED,
                    Intents.REACHABLE_DEVICES,
                    Intents.QUERY,
                ].includes(this.intent)) {
                return await this.forwardRequest(targetDeviceId, true);
            }
            throw this.createError(ErrorCode.GENERIC_ERROR, "Webhook not registered");
        }
        let response;
        try {
            response = JSON.parse(rawResponse.httpResponse.body);
        }
        catch (err) {
            this.logError("Invalid JSON in response", rawResponse.httpResponse.body, err);
            throw this.createError(ErrorCode.GENERIC_ERROR, `Error parsing body: ${rawResponse.httpResponse.body}`, rawResponse.httpResponse.body);
        }
        this.logMessage(`HAAS response received [HTTP:${rawResponse.httpResponse.statusCode}} Retry:${isRetry}]`, response);
        return response;
    }
}
const extractHAVersionFromMdnsRecords = (texts) => {
    for (const text of texts) {
        if (text.startsWith("version=")) {
            return text.split("=")[1];
        }
    }
    return undefined;
};
const getHAVersionFromProxyDevice = (deviceManager) => {
    const proxyDevice = deviceManager.getRegisteredDevices().find((dev) => { var _a, _b;
    // Only the proxy device has scanData
    return (_b = (_a = dev.scanData) === null || _a === void 0 ? void 0 : _a.mdnsScanData) === null || _b === void 0 ? void 0 : _b.texts; });
    if (!proxyDevice) {
        return undefined;
    }
    return extractHAVersionFromMdnsRecords(proxyDevice.scanData.mdnsScanData.texts);
};
const atleastVersion = (haVersion, major, minor) => {
    const parts = haVersion.split(".");
    if (parts.length < 2) {
        return false;
    }
    let numbers;
    try {
        numbers = [parseInt(parts[0]), parseInt(parts[1])];
    }
    catch (err) {
        return false;
    }
    return (
    // If major version is higher
    numbers[0] > major ||
        // same major, higher or equal minor
        (numbers[0] == major && numbers[1] >= minor));
};
const app = new App(VERSION);
app
    .onIdentify(async (request) => {
    const handler = new RequestResponseHandler(Intents.IDENTIFY, request, {
        extractHAVersion: () => {
            var _a;
            return extractHAVersionFromMdnsRecords(((_a = request.inputs[0].payload.device.mdnsScanData) === null || _a === void 0 ? void 0 : _a.data) || []);
        },
    });
    const deviceManager = await handler.getDeviceManager();
    const deviceToIdentify = request.inputs[0].payload.device;
    if (!deviceToIdentify.mdnsScanData ||
        deviceToIdentify.mdnsScanData.data.length === 0) {
        throw handler.createError(ErrorCode.DEVICE_NOT_IDENTIFIED, "No usable mdns scan data");
    }
    if (!deviceToIdentify.mdnsScanData.serviceName.endsWith("._home-assistant._tcp.local")) {
        throw handler.createError(ErrorCode.DEVICE_NOT_IDENTIFIED, `Not Home Assistant type: ${deviceToIdentify.mdnsScanData.serviceName}`);
    }
    const customData = handler.getHassCustomData(deviceManager);
    if (deviceToIdentify.mdnsScanData.txt.uuid &&
        customData.uuid &&
        deviceToIdentify.mdnsScanData.txt.uuid !== customData.uuid) {
        throw handler.createError(ErrorCode.DEVICE_VERIFICATION_FAILED, `UUID does not match.`, deviceManager.getRegisteredDevices());
    }
    return await handler.forwardRequest("");
})
    // Intents targeting the proxy device
    // This used to fix things, in June 2022 it breaks things?
    // .onProxySelected((request) =>
    //   new RequestResponseHandler(Intents.PROXY_SELECTED, request, {
    //     supportedHAVersion: [2022, 3],
    //   }).forwardRequest(request.inputs[0].payload.device.id)
    // )
    .onReachableDevices((request) => new RequestResponseHandler(Intents.REACHABLE_DEVICES, request).forwardRequest(request.inputs[0].payload.device.id))
    // Intents targeting a device in Home Assistant
    .onQuery((request) => new RequestResponseHandler(Intents.QUERY, request).forwardRequest(request.inputs[0].payload.devices[0].id))
    .onExecute((request) => new RequestResponseHandler(Intents.EXECUTE, request).forwardRequest(request.inputs[0].payload.commands[0].devices[0].id))
    .listen()
    .then(() => {
    console.log("Ready!");
})
    .catch((e) => console.error(e));
