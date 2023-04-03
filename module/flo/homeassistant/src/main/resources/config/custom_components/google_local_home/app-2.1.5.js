"use strict";
/// <reference types="@google/local-home-sdk" />
var App = smarthome.App;
var Constants = smarthome.Constants;
var DataFlow = smarthome.DataFlow;
var Execute = smarthome.Execute;
var Intents = smarthome.Intents;
var IntentFlow = smarthome.IntentFlow;
var ErrorCode = IntentFlow.ErrorCode;
const VERSION = "2.1.5";
/** Create and log the error. */
const createError = (requestId, errorCode, msg, ...extraLog) => {
    console.error(requestId, errorCode, msg, ...extraLog);
    return new IntentFlow.HandlerError(requestId, errorCode, msg);
};
/** Get Home Assistant info stored in device custom data. */
const getHassCustomData = (deviceManager, requestId) => {
    for (const device of deviceManager.getRegisteredDevices()) {
        const customData = device.customData;
        if (customData && "webhookId" in customData && "httpPort" in customData) {
            return customData;
        }
    }
    throw createError(requestId, ErrorCode.DEVICE_VERIFICATION_FAILED, `Unable to find HASS connection info.`, deviceManager.getRegisteredDevices());
};
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
const createResponse = (request, payload) => ({
    requestId: request.requestId,
    payload,
});
const forwardRequest = async (intent, request, targetDeviceId, options = {}) => {
    const deviceManager = await app.getDeviceManager();
    const haVersion = (options.extractHAVersion || getHAVersionFromProxyDevice)(deviceManager);
    console.log(`Sending ${intent} to HA ${haVersion}`, request);
    if (options.supportedHAVersion &&
        (!haVersion || !atleastVersion(haVersion, ...options.supportedHAVersion))) {
        console.log("Intent not supported by HA version. Returning empty response");
        return createResponse(request, {});
    }
    const deviceData = getHassCustomData(deviceManager, request.requestId);
    const command = new DataFlow.HttpRequestData();
    command.method = Constants.HttpOperation.POST;
    command.requestId = request.requestId;
    command.deviceId = targetDeviceId;
    command.port = deviceData.httpPort;
    command.path = `/api/webhook/${deviceData.webhookId}`;
    command.data = JSON.stringify(request);
    command.dataType = "application/json";
    command.additionalHeaders = {
        "HA-Cloud-Version": VERSION,
    };
    // console.log(request.requestId, "Sending", command);
    let rawResponse;
    try {
        rawResponse = (await deviceManager.send(command));
    }
    catch (err) {
        console.error(`Error making request: ${err}`);
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
        if (!options.isRetry) {
            await new Promise((resolve) => setTimeout(resolve, 4000));
            return await forwardRequest(intent, request, targetDeviceId, {
                ...options,
                isRetry: true,
            });
        }
        throw createError(request.requestId, ErrorCode.GENERIC_ERROR, "Webhook not registered");
    }
    let response;
    try {
        response = JSON.parse(rawResponse.httpResponse.body);
    }
    catch (err) {
        throw createError(request.requestId, ErrorCode.GENERIC_ERROR, `Error parsing body: ${rawResponse.httpResponse.body}`, rawResponse.httpResponse.body);
    }
    console.log(request.requestId, "Response", response);
    return response;
};
const app = new App(VERSION);
app
    .onIdentify(async (request) => {
    const deviceToIdentify = request.inputs[0].payload.device;
    if (!deviceToIdentify.mdnsScanData ||
        deviceToIdentify.mdnsScanData.data.length === 0) {
        throw createError(request.requestId, ErrorCode.DEVICE_NOT_IDENTIFIED, "No usable mdns scan data");
    }
    if (!deviceToIdentify.mdnsScanData.serviceName.endsWith("._home-assistant._tcp.local")) {
        throw createError(request.requestId, ErrorCode.DEVICE_NOT_IDENTIFIED, `Not Home Assistant type: ${deviceToIdentify.mdnsScanData.serviceName}`);
    }
    const deviceManager = await app.getDeviceManager();
    const customData = getHassCustomData(deviceManager, request.requestId);
    if (deviceToIdentify.mdnsScanData.txt.uuid &&
        customData.uuid &&
        deviceToIdentify.mdnsScanData.txt.uuid !== customData.uuid) {
        throw createError(request.requestId, ErrorCode.DEVICE_VERIFICATION_FAILED, `UUID does not match.`, deviceManager.getRegisteredDevices());
    }
    return await forwardRequest(Intents.IDENTIFY, request, "", {
        extractHAVersion: () => {
            var _a;
            return extractHAVersionFromMdnsRecords(((_a = request.inputs[0].payload.device.mdnsScanData) === null || _a === void 0 ? void 0 : _a.data) || []);
        },
    });
})
    // Intents targeting the proxy device
    .onProxySelected((request) => forwardRequest(Intents.PROXY_SELECTED, request, request.inputs[0].payload.device.id, { supportedHAVersion: [2022, 3] }))
    .onReachableDevices((request) => forwardRequest(Intents.REACHABLE_DEVICES, request, request.inputs[0].payload.device.id))
    // Intents targeting a device in Home Assistant
    .onQuery((request) => forwardRequest(Intents.QUERY, request, request.inputs[0].payload.devices[0].id))
    .onExecute((request) => forwardRequest(Intents.EXECUTE, request, request.inputs[0].payload.commands[0].devices[0].id))
    .listen()
    .then(() => {
    console.log("Ready!");
})
    .catch((e) => console.error(e));
