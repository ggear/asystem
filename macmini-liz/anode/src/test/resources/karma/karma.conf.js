module.exports = function (config) {
    config.set({
        basePath: '',
        frameworks: ['jasmine'],
        files: [
            '../../../../target/package/main/python/anode/web/js/robust-ws.js',
            '../../../../target/package/main/python/anode/web/js/anode.js',
            '../../../../src/test/python/system/system_tests.js',
        ],
        exclude: [],
        preprocessors: {},
        reporters: ['progress'],
        port: 9876,
        colors: false,
        logLevel: config.LOG_INFO,
        autoWatch: false,
        captureTimeout: 10000,
        singleRun: true,
        concurrency: Infinity,
        browsers: ['ChromeHeadless_without_security'],
        customLaunchers: {
            ChromeHeadless_without_security: {
                base: 'ChromeHeadless',
                flags: ['--disable-web-security', '--disable-site-isolation-trials']
            }
        }
    })
}