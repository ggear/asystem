// Google Sheets custom function for the wrangle equity.prices feed.
//
// Setup, once per sheet:
//   1. Extensions > Apps Script, paste this file into Code.gs
//   2. Extensions > Apps Script > Project Settings > Script Properties, add CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET (case-sensitive) from src/may/cloudflare/.env_all_key
//   3. Extensions > Apps Script > Run "installHourlyRefresh" once to install the hourly trigger
//   4. Use as =WRANGLE_PRICE("GOLD", "ASX", $A$1 & $J$3)
//
// Sheets caches a custom function's result against its arguments, so a recalculation with unchanged arguments reuses the cached value rather than re-running the function.
// The optional third argument is ignored by the function and exists purely to break that cache, e.g. =WRANGLE_PRICE(B29, K29, A1) where A1 holds a value that changes,
// such as =NOW() on an hourly recalculation trigger. Changing A1 changes the input signature and forces a genuine re-run.

var WRANGLE_SUFFIX = {
    '': '',
    'ASX': '.AX',
    'LON': '.L',
    'TSE': '.TO',
    'FRA': '.F',
    'NYSE': '',
    'NASDAQ': '',
    'NYSEARCA': '',
    'BATS': ''
};

var WRANGLE_INVALIDATE_SHEET = 'Returns';
var WRANGLE_INVALIDATE_CELL = 'J3';

function WRANGLE_PRICE(symbol, exchange, invalidate) {
    var props = PropertiesService.getScriptProperties();
    var id = props.getProperty('CF_ACCESS_CLIENT_ID');
    var secret = props.getProperty('CF_ACCESS_CLIENT_SECRET');
    if (!id || !secret) throw new Error('Script Properties CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET are not set');
    if (!symbol) throw new Error('symbol is required, e.g. =WRANGLE_PRICE("BHP", "ASX")');

    var key = String(exchange || '').trim().toUpperCase();
    var suffix = WRANGLE_SUFFIX[key];
    if (suffix === undefined) throw new Error('unknown exchange [' + key + ']');

    var target = String(symbol).trim() + suffix;
    var started = new Date().getTime();
    var response = UrlFetchApp.fetch(
        'https://prices.janeandgraham.com/' + encodeURIComponent(target), {
            headers: {
                'CF-Access-Client-Id': id,
                'CF-Access-Client-Secret': secret
            },
            muteHttpExceptions: true
        });
    var elapsed = new Date().getTime() - started;

    if (response.getResponseCode() != 200) {
        console.log('WRANGLE_PRICE [%s] failed [%s] in [%sms]', target, response.getResponseCode(), elapsed);
        throw new Error(response.getContentText());
    }

    var price = JSON.parse(response.getContentText()).price;
    console.log('WRANGLE_PRICE [%s] price [%s] in [%sms]', target, price, elapsed);
    return price;
}

function refreshWranglePrices() {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(WRANGLE_INVALIDATE_SHEET);
    if (!sheet) throw new Error('sheet [' + WRANGLE_INVALIDATE_SHEET + '] not found');
    sheet.getRange(WRANGLE_INVALIDATE_CELL).setValue(new Date());
    console.log('refreshWranglePrices: bumped %s!%s', WRANGLE_INVALIDATE_SHEET, WRANGLE_INVALIDATE_CELL);
}

function installHourlyRefresh() {
    ScriptApp.getProjectTriggers().forEach(function (trigger) {
        if (trigger.getHandlerFunction() === 'refreshWranglePrices') {
            ScriptApp.deleteTrigger(trigger);
        }
    });
    ScriptApp.newTrigger('refreshWranglePrices')
        .timeBased()
        .everyHours(1)
        .create();
    console.log('installHourlyRefresh: hourly trigger installed');
}
