function decodeDatumField(datumField) {
    var ESCAPE_SWAPS = {
        "_": ".",
        ".": "_"
    };
    var ESCAPE_SEQUENCES = {
        "__": "_",
        "_X": ".",
        "_D": "-",
        "_P": "%"
    };
    var datumFields = datumField.split("__");
    for (var i = 0; i < datumFields.length; i++) {
        for (var escaped in ESCAPE_SEQUENCES) {
            datumFields[i] = datumFields[i].split(escaped).join(ESCAPE_SEQUENCES[escaped])
        }
    }
    var datumFieldDecodedChars = datumFields.join("_").split('');
    for (var i = 0; i < datumFieldDecodedChars.length; i++) {
        var swapped = false;
        for (var swap in ESCAPE_SWAPS) {
            if (!swapped && datumFieldDecodedChars[i] === swap) {
                datumFieldDecodedChars[i] = ESCAPE_SWAPS[swap];
                swapped = true
            }
        }
    }
    return decodeURIComponent(datumFieldDecodedChars.join(""))
}

function ANode(uri, onopen, onclose, onmessage) {

    if (!(this instanceof ANode)) {
        throw "Anonde constructor not used";
    }

    var outer = this;
    var uriBase = uri.substring(uri.indexOf("//") + 2, uri.length);
    var uriHostPort = uriBase.substring(0, uriBase.indexOf("/"));
    var uriParameters = uriBase.substring(uriBase.indexOf("/") + 1, uriBase.length);

    this.restfulUri = "http://" + uriHostPort + "/rest/";
    this.metadataUri = "http://" + uriHostPort + "/js/metadata/datum.avsc";
    this.webSocketUri = "ws://" + uriHostPort + "/ws/" + uriParameters;

    this.metadata = this.metadataRequest();
    this.orderingIndexes = {};
    this.orderingIndexes["data_metric"] = {};
    var data_metric = this.metadata["fields"][4]["type"]["symbols"];
    for (var i = 1; i < data_metric.length; i++) {
        this.orderingIndexes["data_metric"][decodeDatumField(data_metric[i])] = i * 100000;
    }
    this.orderingIndexes["data_type"] = {};
    var data_type = this.metadata["fields"][6]["type"]["symbols"];
    for (var i = 1; i < data_type.length; i++) {
        this.orderingIndexes["data_type"][decodeDatumField(data_type[i])] = i * 10000;
    }
    this.orderingIndexes["bin_unit"] = {};
    var bin_unit = this.metadata["fields"][14]["type"]["symbols"];
    for (var i = 1; i < bin_unit.length; i++) {
        this.orderingIndexes["bin_unit"][decodeDatumField(bin_unit[i])] = i * 1000;
    }

    this.connected = false;
    this.webSocket = new WebSocket(this.webSocketUri);

    this.webSocket.onopen = function () {
        outer.connected = true;
        if (typeof onopen !== "undefined") {
            try {
                onopen(outer.metadata);
            } catch (error) {
                console.log(error)
            }
        }
    };

    this.webSocket.onmessage = function (frame) {
        if (typeof onmessage !== "undefined") {
            try {
                onmessage(outer.toDatum(frame.data));
            } catch (error) {
                console.log(error)
            }
        }
    };

    this.webSocket.onclose = function () {
        outer.connected = false;
        if (typeof onclose !== "undefined") {
            try {
                onclose();
            } catch (error) {
                console.log(error)
            }
        }
    };

    this.toDatum = function (datumJson) {
        var datum = JSON.parse(datumJson);
        datum.ui_id_sans_bin = "datums_" + (datum.data_metric + "_").replace(/\//g, "_").replace(/\./g, "_").toLowerCase();
        datum.ui_id = (datum.ui_id_sans_bin + datum.bin_width + "_" + datum.bin_unit).replace(/\//g, "_").replace(/\./g, "_").toLowerCase();
        datum.order_index = this.orderingIndexes["data_metric"][datum.data_metric] + this.orderingIndexes["data_type"][datum.data_type] +
            this.orderingIndexes["bin_unit"][datum.bin_unit] + datum.bin_width;
        datum.data_timeliness = "";
        //noinspection EqualityComparisonWithCoercionJS,EqualityComparisonWithCoercionJS,EqualityComparisonWithCoercionJS,EqualityComparisonWithCoercionJS,EqualityComparisonWithCoercionJS
        if (((datum.data_temporal == "current" || datum.data_temporal == "repeat" || datum.data_temporal == "derived") && datum.data_type == "point") || datum.bin_width == 0) {
            datum.data_timeliness = "now";
        } else {
            //noinspection EqualityComparisonWithCoercionJS,EqualityComparisonWithCoercionJS,EqualityComparisonWithCoercionJS,EqualityComparisonWithCoercionJS
            if (datum.data_type != "point" && datum.data_type != "integral" && datum.data_type != "enumeration" && datum.data_type != "epoch") {
                datum.data_timeliness = datum.data_type + " ";
            }
            if (datum.bin_width > 1) {
                //noinspection EqualityComparisonWithCoercionJS
                if (datum.data_temporal == "forecast") {
                    //noinspection EqualityComparisonWithCoercionJS
                    if (datum.bin_unit == "day") {
                        //noinspection EqualityComparisonWithCoercionJS
                        if (datum.bin_width == 2) {
                            datum.data_timeliness += "tomorrow";
                        } else { //noinspection EqualityComparisonWithCoercionJS
                            if (datum.bin_width == 3) {
                                datum.data_timeliness += "overmorrow";
                            }
                        }
                    } else { //noinspection EqualityComparisonWithCoercionJS
                        if (datum.bin_unit == "day-time") {
                            //noinspection EqualityComparisonWithCoercionJS
                            if (datum.bin_width == 2) {
                                datum.data_timeliness += "tomorrow day time";
                            } else { //noinspection EqualityComparisonWithCoercionJS
                                if (datum.bin_width == 3) {
                                    datum.data_timeliness += "overmorrow day time";
                                }
                            }
                        } else { //noinspection EqualityComparisonWithCoercionJS
                            if (datum.bin_unit == "night-time") {
                                //noinspection EqualityComparisonWithCoercionJS
                                if (datum.bin_width == 2) {
                                    datum.data_timeliness += "tomorrow night time";
                                } else { //noinspection EqualityComparisonWithCoercionJS
                                    if (datum.bin_width == 3) {
                                        datum.data_timeliness += "overmorrow night time";
                                    }
                                }
                            }
                        }
                    }
                } else {
                    datum.data_timeliness += "over the last " + datum.bin_width + " " + datum.bin_unit + "s";
                }
            } else {
                //noinspection EqualityComparisonWithCoercionJS
                if (datum.bin_unit == "day") {
                    datum.data_timeliness += "today";
                } else { //noinspection EqualityComparisonWithCoercionJS
                    if (datum.bin_unit == "day-time") {
                        datum.data_timeliness += "during the day";
                    } else { //noinspection EqualityComparisonWithCoercionJS
                        if (datum.bin_unit == "night-time") {
                            datum.data_timeliness += "over night";
                        } else { //noinspection EqualityComparisonWithCoercionJS
                            if (datum.bin_unit == "all-time") {
                                datum.data_timeliness += "for all time";
                            } else {
                                datum.data_timeliness += "this " + datum.bin_unit;
                            }
                        }
                    }
                }
            }
        }
        return datum;
    }

}

ANode.prototype.isConnected = function () {
    return this.connected;
};

ANode.prototype.metadataRequest = function () {
    var metadata = null;
    var metadataHttpRequest = new XMLHttpRequest();
    metadataHttpRequest.open("GET", this.metadataUri, false);
    metadataHttpRequest.onreadystatechange = function () {
        //noinspection EqualityComparisonWithCoercionJS
        if (metadataHttpRequest.readyState == 4) {
            //noinspection EqualityComparisonWithCoercionJS
            if (metadataHttpRequest.status == 200) {
                metadata = JSON.parse(metadataHttpRequest.responseText);
            }
        }
    };
    metadataHttpRequest.send();
    return metadata;
};

ANode.prototype.restfulRequest = function (parameters, onmessage) {
    var restfulHttpRequest = new XMLHttpRequest();
    restfulHttpRequest.open("GET", this.restfulUri + (parameters ? ("?" + parameters) : ""), true);
    restfulHttpRequest.onreadystatechange = function () {
        //noinspection EqualityComparisonWithCoercionJS
        if (restfulHttpRequest.readyState == 4) {
            //noinspection EqualityComparisonWithCoercionJS
            if (restfulHttpRequest.status == 200) {
                onmessage(JSON.parse(restfulHttpRequest.responseText));
            }
        }
    };
    restfulHttpRequest.send();
};

