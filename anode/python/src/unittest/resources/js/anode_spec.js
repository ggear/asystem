WEB_PORT = 8091;
ANODE_WARMUP_PERIOD = 6000;
jasmine.DEFAULT_TIMEOUT_INTERVAL = 10000;


describe('ANode', function () {

    var metrics;
    var metrics_anode;

    beforeAll(function (done) {
        metrics = 0;
        metrics_anode = 0;
        setTimeout(function () {
            new ANode(connectionUri("")).restfulRequest("metrics=anode", function (datums) {
                for (var i = 0; i < datums.length; i++) {
                    metrics++;
                    if (datums[i].data_metric.indexOf("metrics", this.length - "metrics".length) !== -1) {
                        metrics_anode += datums[i].data_value;
                    }
                }
                done();
            });
        }, ANODE_WARMUP_PERIOD);
    });

    it('connection', function (done) {
        connectionTest(done, connectionUri(""))
    });

    it('message metrics bins', function (done) {
        messageTest(done, connectionUri("metrics=power.production.inverter&bins=1second"), 1)
    });

    it('message metrics types', function (done) {
        messageTest(done, connectionUri("metrics=power.production.inverter&types=point"), 1)
    });

    it('message metrics types bins', function (done) {
        messageTest(done, connectionUri("metrics=power.production.inverter&types=point&bins=1second"), 1)
    });

    it('message metrics metrics types bins', function (done) {
        messageTest(done, connectionUri("metrics=power.production.inverter&metrics=&types=point&bins=1second"), 1)
    });

    it('message metrics metrics types types bins', function (done) {
        messageTest(done, connectionUri("metrics=power.production.inverter&metrics=&types=point&types=some_nonexistant_type&bins=1second"), 1)
    });

    it('message metrics metrics types types bins bins', function (done) {
        messageTest(done, connectionUri("metrics=power.production.inverter&metrics=&types=point&bins=1second&bins=some_nonexistant_bin"), 1)
    });

    it('message metrics metrics types bins', function (done) {
        messageTest(done, connectionUri("metrics=power.production.inverter&metrics=power.export.grid&metrics=&types=point&bins=1second"), 2)
    });

    it('message metrics', function (done) {
        messageTest(done, connectionUri("metrics=power.production.inverter"), 3)
    });

    it('message bins', function (done) {
        messageTest(done, connectionUri("bins=1second"), 9)
    });

    it('message metrics', function (done) {
        messageTest(done, connectionUri("metrics=power"), 21)
    });

    it('message something ', function (done) {
        messageTest(done, connectionUri("something=else"), metrics)
    });

    // TODO: Re-enable once publish reliability resolved
    // it('message publish', function (done) {
    //     restTest(done, connectionUri("scope=publish", true), 0)
    // });

    it('message', function (done) {
        messageTest(done, connectionUri(""), metrics)
    });


});

connectionUri = function (parameters, isRest) {
    return "http://localhost:" + WEB_PORT +
        ((typeof (isRest) === 'undefined' || !isRest) ? "/" : "/rest/") +
        (parameters ? ("?" + parameters) : "");
};


connectionTest = function (done, url) {
    var anode = new ANode(url,
        function () {
            expect(anode.isConnected()).toBe(true);
            done();
        });
};

messageTest = function (done, url, messagesExpected) {
    var messagesReceived = 0;
    new ANode(url,
        function () {
        },
        function () {
        },
        function (datum) {
            expect(datum).not.toEqual(null);
            expect(datum.data_metric).not.toEqual(null);
            expect(datum.data_metric).not.toEqual("");
            if (++messagesReceived >= messagesExpected)
                done();
        });
};

restTest = function (done, url, messagesExpected) {
    var request = new XMLHttpRequest();
    request.open("GET", url);
    request.onreadystatechange = function () {
        if (request.readyState === 4) {
            if (request.status === 200) {
                if (JSON.parse(request.responseText).length === messagesExpected)
                    done();
            }
        }
    };
    request.send();
};


